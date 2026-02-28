import re
import json
import manuscripts

# L'OCR n'est pas d'aussi bonne qualité que prévu...
CATALOG_PATH = "corpus\catalog\CatalogOfRomances_vol_1.txt"


def verify_all_pages():
    # Vérifier que l'on obtienne bien un pointeur pour segmenter chaque page
    # sans en oublier etc...
    # suffit pas, peut y avoir des erreurs d'OCR 
    # et le pattern ne les détecte pas
    # il va en manquer pour les pages qui commencent par un gros titre en gras sans nombre...

    #pattern_page_titles = r"^(\d{1,3}\s+[A-Z\s]+\.|[A-Z\s]+\.\s+\d{1,3})"
    pattern_page_titles = r"^\s*(?=.*[A-Z].*[A-Z])(\d{1,3}[\s\W]+[A-Z\d\s\W]+|[A-Z\d\s\W]+?[\s\W]+\d{1,3})\s*$"
    detect_page_titles = re.findall(pattern_page_titles, catalog, flags=re.MULTILINE)
    #print(detect_page_titles)
    # print(len(detect_page_titles))
    # i = 1
    # updated_detect_page_titles = []
    # for match in detect_page_titles:
    #     #if str(i) in match[0:3] or str(i) in match[-3:]: # trop naïf
    #     #    updated_detect_page_titles.append(match)
    #     #    i += 1
    #     pass#print(int(match[0:3]))
    # #print(len(updated_detect_page_titles))
    return detect_page_titles # il en manque

def segment_wrt_page():
    # Segment the catalog with respect to: page
    #utiliser le .xml (HOCR)
    pass

def segment_wrt_opera(catalog, sortie):
    # Segment the catalog with respect to: opera
    pass


if __name__ == '__main__':
    
    #print(manuscripts.CORRESPONDENCE_OPERA_MSS)

    with open(CATALOG_PATH, 'r', encoding='utf-8') as cata:
        catalog_lines = cata.readlines()
        catalog = cata.read()

    #segment_wrt_opera(catalog)
    #print(len(catalog))

    detected_ctn = [0] * len(manuscripts.OPERA_categories)
    for idx, key in enumerate(manuscripts.OPERA_categories):
        # On fait le choix de conserver  les erreurs d'OCR
        # pour n'avoir qu'une seule et unique représentation;
        # au besoin, on donnera une sortie proprifée (uniquement 
        # à la fin fin fin mais on manipule une seule représentation!)

        for idx_line in range(1, len(catalog_lines) - 1):
            
            if catalog_lines[idx_line].startswith(key) and catalog_lines[idx_line - 1] == "\n" and catalog_lines[idx_line + 1] == "\n":
                detected_ctn[idx] += 1
                #print(catalog_lines[idx_line])

                maj_key = key.upper()
                manuscripts.CORRESPONDENCE_OPERA_MSS[key][catalog_lines[idx_line][:-1]] = {
                    'line' : idx_line
                    # ajouter le 'corrected_name' (sans erreur OCR)
                }

    print(detected_ctn)
    print(manuscripts.OPERA_count)
    print([len(manuscripts.CORRESPONDENCE_OPERA_CORRECTED_MSS[manus]) for manus in manuscripts.CORRESPONDENCE_OPERA_CORRECTED_MSS])
    # Pas dégueu mais peut mieux faire:
        # [97, 83, 106, 16, 15, 0, 20, 153, 10]
        # [103, 92, 99, 13, 21, 6, 17, 149, 6]
    # un poil mieux :
        # [94, 70, 95, 14, 13, 0, 15, 142, 7]
        # [103, 92, 99, 13, 21, 6, 17, 149, 6]


    #print(manuscripts.CORRESPONDENCE_OPERA_MSS)
    # On ajoute à la main les entrées manquantes et celles en trop
    #manuscripts.CORRESPONDENCE_OPERA_MSS["Royal"]["Royal  16.  C.  zxiii.    ff.  2-69  b. "] = {
    #    'line' : '3817'
    #}

    with open("test.txt", 'w', encoding='utf-8') as f:
        f.write(json.dumps(manuscripts.CORRESPONDENCE_OPERA_CORRECTED_MSS))

    # Ceux qui manquent (page):
        # Royal:
        #           26, 
