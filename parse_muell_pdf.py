#!/usr/bin/env python3
from datetime import datetime

import camelot
import pandas as pd


def zip_to_str_list(l):
    """takes list/tuple of lists and returns list of strings
    where the elements are commaseperated strings"""
    rr = []
    for s in zip(*l):
        r = ""
        for c in s:
            r+=str(c)+","
        rr.append(r[:-1])
    return rr
    
def parse_calendar(fn, year) -> list:
    """PDF parsen. fn = filename"""
    
    # table_areas
    t_top       = 535
    t_bottom    = 156
    t_width     = 138

    x1 = [9,144,282,420,560,698]
    y1 = [t_top for i in range(len(x1))]
    x2 = [i+t_width for i in x1]
    y2 = [t_bottom for i in range(len(x1))]

    table_areas = zip_to_str_list([x1, y1, x2, y2])
    
    # columns
    columns_table_1 = [30, 44, 75, 112]
    offset = 15
    column_space = []
    for i in columns_table_1:
        column_space.append(i-offset)
    columns = []
    for i in x1:
        columns.append(str([i+c for c in column_space]).replace("[", "").replace("]", ""))

    # camelot parser
    tables_lattice = camelot.read_pdf(fn,
                            pages="1, 2",
                            flavor='stream',
                            table_areas = table_areas,
                            column_tol = 0.5,
                            row_tol = 4, # die Kalenderwochen mit in die Zeile packen
                            columns = columns,
                            # split_text = True,
                            layout_kwargs={
                                # 'word_margin'   : 0.05,
                                'char_margin'   : 0.02,
                            }
                            )
    # eigene Liste bauen
    df_list = []
    for i in tables_lattice:
        df = i.df
        df.columns = ["TagNr", "Wochentag", "Restmüll", "Papiermüll", "Gelber Sack"]
        df_list.append(df)
            
    # zu datetime als index konvertieren
    for c, i in enumerate(df_list, 1):
        # datum_series = pd.Series(name="Datum")
        datumsliste = []
        for tag_nr in i['TagNr']:
            datum = datetime(year, c, int(tag_nr)) 
            datumsliste.append(datum)
        i['Datum'] = datumsliste
        i.index = i['Datum']
        i.drop('Datum', axis=1, inplace=True)
        i.drop('TagNr', axis=1, inplace=True)
        
    # einzelnen df fürs ganze Jahr bauen
    df = pd.concat(df_list)
    
    return df

# crontab https://crontab.guru/
# maybe check this out https://cronitor.io/sign-up
# $RANDOM is an internal Bash function (not a constant) that returns a pseudorandom [1] integer in the range 0 - 32767.
# It should not be used to generate an encryption key.
# 0 0 * * 5 sleep "$(((($RANDOM % 48)*3600 + $RANDOM % 60))"; /path/to/executable
# jeden Freitag

def main():
    
    YEAR = 2023

    # parsen
    fn = "./Abfuhrkalender_2023.pdf"
    df = parse_calendar(fn, year = YEAR)
        
    # csv schreiben
    df.to_csv(f"AK_{YEAR}_komplett.csv")
    print(f"------> AK_{YEAR}_komplett.csv", "saved")
    
if __name__ == "__main__":
    main()
