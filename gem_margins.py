import pandas as pd
import data_handler as dh

pd.options.mode.chained_assignment = None

import sqlite3

GEM_EXPERIENCE_AWAKENED = 1920762677  # to level 5; #TODO: awakened gems seem to have different xp requirements?
GEM_EXPERIENCE_ENLEMPENH = 1666045137  # to level 3; for enhance, empower and enlighten
GEM_EXPERIENCE_BLOODANDSAND = 529166003  # to level 6;
GEM_EXPERIENCE_BRANDRECALL = 341913067  # to level 6
GEM_EXPERIENCE_REGULAR = 1666045137  # to level 3;
MAX_EXP = max(GEM_EXPERIENCE_AWAKENED, GEM_EXPERIENCE_ENLEMPENH, GEM_EXPERIENCE_BLOODANDSAND,
              GEM_EXPERIENCE_BRANDRECALL, GEM_EXPERIENCE_REGULAR)

GEM_EXPERIENCE = {"awakened": GEM_EXPERIENCE_AWAKENED,
                  "enlempenh": GEM_EXPERIENCE_ENLEMPENH,
                  "bloodandsand": GEM_EXPERIENCE_BLOODANDSAND,
                  "brandrecall": GEM_EXPERIENCE_BRANDRECALL,
                  "regular": GEM_EXPERIENCE_REGULAR,
                  "awakened_norm": GEM_EXPERIENCE_AWAKENED / MAX_EXP,
                  "enlempenh_norm": GEM_EXPERIENCE_ENLEMPENH / MAX_EXP,
                  "bloodandsand_norm": GEM_EXPERIENCE_BLOODANDSAND / MAX_EXP,
                  "brandrecall_norm": GEM_EXPERIENCE_BRANDRECALL / MAX_EXP,
                  "regular_norm": GEM_EXPERIENCE_REGULAR / MAX_EXP,
                  }


def get_ex_value(df):
    ex_value = df.loc['Exalted Orb'][0]
    df['value_exalted'] = df['value'].div(ex_value)
    return df


def add_gem_colors(df):
    df_colors = pd.read_excel('utility/gem_colors.xlsx')
    # drop zeros from excel
    df_colors[(df_colors != 0).all(1)]
    df_colors = df_colors[~(df_colors == 0).any(axis=1)]
    gem_colors = df_colors.values.tolist()
    for gem in gem_colors:
        # print(gem[0])
        df.loc[df['name'].str.contains(gem[0]), 'gem_color'] = gem[1]

    return df


def calculate_chaos_values(df):
    unique_names = df.drop_duplicates(subset="name")
    names = unique_names["name"].tolist()

    # create a new dataframe with all columns that will be filled using the loop below
    df_analyzed = df[0:0]

    for idx, gems in enumerate(names):
        # iterate trough every gem in the gem list (e.g. Lightning Strike, Hatred, ...)
        df_ = df[df['name'] == gems]

        # find the cheapest entry in the group and use it as a basis
        df_min = df_[df_.gemQuality == df_.gemQuality.min()]
        df_min = df_min[df_min.gemLevel == df_min.gemLevel.min()]
        df_min = df_min[df_min.value_chaos == df_min.value_chaos.min()]
        df_min = df_min[df_min.corrupted == df_min.corrupted.min()]

        # iterate through every single gem entry for a give gem (e.g. 8/0, 16/0 and 20/20 for Lightning Strike)
        for i in range(df_.shape[0]):
            df_gem = df_.iloc[[i]]
            # calculate the important metrics
            buy_c = df_min["value_chaos"].values[0]
            sell_c = df_gem["value_chaos"].values[0]
            margin_c = sell_c - buy_c
            roi_c = margin_c / buy_c

            # add them to the highest level / quality gem dataframe
            df_gem["buy_c"] = buy_c
            df_gem["sell_c"] = sell_c
            df_gem["margin_c"] = margin_c
            df_gem["roi"] = roi_c

            # upgrade path
            # TODO: Add differentiation between corrupted and none-corrupted?
            if df_gem["corrupted"].values[0]:
                df_gem["upgrade_path"] = '[' + str(df_min['gemLevel'].values[0]) \
                                         + '/' + str(df_min['gemQuality'].values[0]) \
                                         + '] -> [' + str(df_gem['gemLevel'].values[0]) \
                                         + '/' + str(df_gem['gemQuality'].values[0]) + '] ©'
            else:
                df_gem["upgrade_path"] = '[' + str(df_min['gemLevel'].values[0]) \
                                         + '/' + str(df_min['gemQuality'].values[0]) \
                                         + '] -> [' + str(df_gem['gemLevel'].values[0]) \
                                         + '/' + str(df_gem['gemQuality'].values[0]) + ']'

            # append the resulting dataframe
            df_analyzed = pd.concat([df_analyzed, df_gem], ignore_index=True)

    return df_analyzed


def calculate_exalted_values(df, C_TO_EX):
    df['buy_ex'] = df['buy_c'].div(C_TO_EX)
    df['sell_ex'] = df['sell_c'].div(C_TO_EX)
    df['margin_ex'] = df['margin_c'].div(C_TO_EX)

    return df


def calculate_roi_norm_and_ranking(df):
    # --- normalize roi depending on xp required ---
    # normalize all gems with regular rating
    # TODO: This should be individual, e.g., 8/0 -> 20/20 != 16/0 -> 20/20
    df['margin_gem_specific'] = df['margin_ex'] / GEM_EXPERIENCE['regular_norm']
    df.loc[df['name'].str.contains("Awakened"), 'margin_gem_specific'] = df['margin_ex'] / GEM_EXPERIENCE[
        'awakened_norm']
    df.loc[df['name'].str.contains("Enlighten"), 'margin_gem_specific'] = df['margin_ex'] / GEM_EXPERIENCE[
        'enlempenh_norm']
    df.loc[df['name'].str.contains("Empower"), 'margin_gem_specific'] = df['margin_ex'] / GEM_EXPERIENCE[
        'enlempenh_norm']
    df.loc[df['name'].str.contains("Enhance"), 'margin_gem_specific'] = df['margin_ex'] / GEM_EXPERIENCE[
        'enlempenh_norm']
    df.loc[df['name'] == "Blood and Sand", 'margin_gem_specific'] = df['margin_ex'] / GEM_EXPERIENCE[
        'bloodandsand_norm']
    df.loc[df['name'] == "Brand Recall", 'margin_gem_specific'] = df['margin_ex'] / GEM_EXPERIENCE['brandrecall_norm']

    # rank entries after roi
    df["ranking_from_margin_gem_specific"] = df['margin_ex'].rank(ascending=False)
    df["ranking_from_roi"] = df['roi'].rank(ascending=False)

    # sort out all rows with no return of investment (margin 0 or even negative)
    df = df[df["roi"] > 0]

    return df


def remove_low_confidence(df, list_cnt):
    unique_gems = list(df['name'].unique())
    skills_to_keep, skills_to_delete = [], []

    for name in unique_gems:
        df_ = df[(df['name'] == name)]
        cnt = list(df_["listingcount"])
        if cnt[0] > list_cnt:
            skills_to_keep.append(name)

    df_conf = df[df['name'].isin(skills_to_keep)]

    return df_conf


def calculate_margins():
    dict_cur = dh.load_raw_dict(type="Currency")
    data_cur = pd.DataFrame.from_dict(dict_cur, orient="index")
    dict_gem = dh.load_raw_dict(type="Gems")
    data_gem = pd.DataFrame.from_dict(dict_gem, orient="index")

    # --- currency ---
    C_TO_EX = data_cur[data_cur['name'] == "Exalted Orb"]['value_chaos'].values[0]

    # --- gems ---
    # sort gems
    df = data_gem.sort_values(['skill', 'qualityType', 'gemLevel'], ascending=[True, True, False])
    # remove vaal skill gems
    df = df[~df.name.str.contains("Vaal")]

    # df["gem_info"] = ""
    df["upgrade_path"] = ""
    df["buy_c"] = ""
    df["sell_c"] = ""
    df["margin_c"] = ""
    df["buy_ex"] = ""
    df["sell_ex"] = ""
    df["margin_ex"] = ""
    df["margin_gem_specific"] = ""
    df["roi"] = ""
    df["ranking_from_roi"] = ""
    df["gem_color"] = ""

    df = calculate_chaos_values(df)

    df = calculate_exalted_values(df, C_TO_EX)

    df = calculate_roi_norm_and_ranking(df)

    df = add_gem_colors(df)

    # todo: save df to json here
    gems_analyzed = df.to_dict(orient="index")
    dh.save_json(gems_analyzed)
