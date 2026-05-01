import sys
import json
from tqdm import tqdm
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
import manuscripts

# OOPS...


# Supposons que les variables suivantes sont importées de votre module
# OPERA_categories = manuscripts.OPERA_categories
# CORRESPONDENCE_OPERA_CORRECTED_MSS = manuscripts.CORRESPONDENCE_OPERA_CORRECTED_MSS

PATH_FILE = "corpus\\catalog\\CatalogOfRomances_vol_1_with_confidence.xml"

# (1) Lire le XML
with open(PATH_FILE, 'r', encoding='utf-8') as f:
    data = f.read()

Bs_data = BeautifulSoup(data, "xml")
PAGES = Bs_data.find_all("OBJECT")
VOLUME_1_PAGES = PAGES[25:980]

# -- PRÉPARATION ET TRI DES DONNÉES --
all_opera_items = []
for opera_cat, items in manuscripts.CORRESPONDENCE_OPERA_CORRECTED_MSS.items():
    for item in items:
        all_opera_items.append({
            'cat': opera_cat,
            'name': item['name'],
            'page': item['page'],
            'key': f"{opera_cat}_{item['name']}_{item['page']}"
        })

# Sécurité : Tri global par numéro de page pour respecter l'ordre du livre
all_opera_items.sort(key=lambda x: x['page'])
print(f"{len(all_opera_items)} œuvres triées par page (de {all_opera_items[0]['page']} à {all_opera_items[-1]['page']})")


def is_centered(x_min, page_num):
    """
    Détermine si une ligne est centrée en fonction de la position x_min de son premier mot.
    (Coordonnées basées sur les observations du prompt)
    """
    if page_num % 2 == 0:
        # Pages paires : le texte non centré commence vers 441 ou 541. 
        # Un titre centré aura un x_min nettement supérieur (ex: > 800)
        return x_min > 800
    else:
        # Pages impaires : le texte non centré commence vers 777 ou 915.
        # Un titre centré aura un x_min nettement supérieur (ex: > 1200)
        return x_min > 1200


# def find_operaTexte(current_item, next_item):
#     """
#     Extrait le texte d'une œuvre (2) en repérant le titre centré (avec similarité OCR),
#     (3) continue l'extraction et s'arrête dès que le titre de l'œuvre suivante est détecté 
#     ou qu'on dépasse la page limite.
#     """
#     start_page = current_item['page']
#     current_name = current_item['name']
    
#     # Sécurité : Si on a une oeuvre suivante, on s'arrête à sa page.
#     # Sinon, on donne une limite arbitraire (ex: +20 pages).
#     end_page = next_item['page'] if next_item else start_page + 20
#     next_name = next_item['name'] if next_item else ""
    
#     extracted_text = []
#     capturing = False
    
#     # L'index du tableau VOLUME_1_PAGES : la page 26 correspond à l'index 0
#     # Donc index = page - 26
#     offset = 26 
    
#     for page_num in range(start_page, end_page + 1):
#         page_idx = page_num - offset
        
#         # Précaution si l'index déborde
#         if page_idx < 0 or page_idx >= len(VOLUME_1_PAGES):
#             break
            
#         page_node = VOLUME_1_PAGES[page_idx]
#         lines = page_node.find_all("LINE")
        
#         for line in lines:
#             words = line.find_all("WORD")
#             if not words:
#                 continue
            
#             line_text = " ".join([w.text for w in words]).strip()
#             if not line_text:
#                 continue
            
#             # Récupération de x_min pour vérifier le centrage
#             coords = words[0].get("coords")
#             x_min = int(coords.split(',')[0]) if coords else 0
            
#             centered = is_centered(x_min, page_num)
#             centered=True # centered marche pas, à corriger plus tard.

#             # --- CONDITION D'ARRÊT ---
#             # Si nous sommes en train de capturer, qu'il y a une oeuvre suivante
#             # et que nous sommes sur la page de début de cette oeuvre suivante
#             if capturing and next_item and page_num == end_page:
#                 if centered:
#                     # Calcul du score OCR pour le titre suivant
#                     score_next = SequenceMatcher(None, next_name.lower(), line_text.lower()).ratio()
#                     if score_next > 0.4:  # Seuil de tolérance (40% de ressemblance suffit souvent pour l'OCR)
#                         capturing = False
#                         break # On stoppe la boucle des lignes
                        
#             # --- CONDITION DE DÉMARRAGE ---
#             # Si on n'a pas encore commencé la capture et qu'on est sur la page de départ
#             if not capturing and page_num == start_page:
#                 if centered:
#                     # Calcul du score OCR pour le titre actuel
#                     score_curr = SequenceMatcher(None, current_name.lower(), line_text.lower()).ratio()
#                     if score_curr > 0.4:
#                         capturing = True
#                         extracted_text.append(line_text) # Optionnel : inclure le titre
#                         continue
            
#             # --- SAUVEGARDE DU TEXTE ---
#             if capturing:
#                 extracted_text.append(line_text)
        
#         # Si la capture a été arrêtée sur la `end_page`, on ne lit pas les pages suivantes
#         if not capturing and next_item and page_num == end_page:
#             break

#     return "\n".join(extracted_text)

def find_operaTexte(current_item, next_item):
    """
    Extrait uniquement le texte probable compris entre la page de l'œuvre actuelle 
    et la page de l'œuvre suivante.
    """
    start_page = current_item['page']
    current_name = current_item['name']
    
    # La page de fin est strictement celle de l'œuvre suivante (ou une limite arbitraire pour la dernière œuvre)
    end_page = next_item['page'] if next_item else min(start_page + 20, len(VOLUME_1_PAGES) + 25)
    next_name = next_item['name'] if next_item else ""
    
    extracted_text = []
    capturing = False
    
    # L'index du tableau VOLUME_1_PAGES : la page 26 correspond à l'index 0
    offset = 0 
    
    # On itère EXCLUSIVEMENT sur la plage de pages probable
    for page_num in range(start_page, end_page + 1):
        page_idx = page_num - offset
        
        # Précaution si l'index déborde des pages disponibles
        if page_idx < 0 or page_idx >= len(VOLUME_1_PAGES):
            continue
            
        page_node = VOLUME_1_PAGES[page_idx]
        lines = page_node.find_all("LINE")
        
        for line in lines:
            words = line.find_all("WORD")
            if not words:
                continue
            
            line_text = " ".join([w.text for w in words]).strip()
            if not line_text:
                continue
            
            # Récupération de x_min pour vérifier si le texte est centré
            coords = words[0].get("coords")
            x_min = int(coords.split(',')[0]) if coords else 0
            centered = is_centered(x_min, page_num)
            
            # Si on est sur la page de fin et qu'on repère le titre de l'œuvre suivante
            if capturing and next_item and page_num == end_page:
                if centered:
                    score_next = SequenceMatcher(None, next_name.lower(), line_text.lower()).ratio()
                    if score_next > 0.4:  # Le titre suivant est repéré, on arrête l'aspiration !
                        capturing = False
                        break # Sort de la boucle des lignes
                        
            # Si on est sur la page de départ et qu'on cherche le titre
            if not capturing and page_num == start_page:
                if centered:
                    score_curr = SequenceMatcher(None, current_name.lower(), line_text.lower()).ratio()
                    if score_curr > 0.4:
                        capturing = True
                        extracted_text.append(line_text) # Optionnel: inclure le titre
                        continue
            
            # Si le titre de départ n'a pas été repéré (OCR trop mauvais), 
            # mais qu'on a dépassé la page de départ, on force la capture du texte probable.
            if not capturing and start_page < page_num <= end_page:
                capturing = True

            # --- SAUVEGARDE DU TEXTE ---
            if capturing:
                extracted_text.append(line_text)
        
        # Si on est sur la page de fin et qu'on a arrêté de capturer (titre suivant trouvé),
        # il est inutile d'analyser le reste de la page
        if not capturing and page_num == end_page:
            break

    return "\n".join(extracted_text)



# -- EXTRACTION --
segment_text_by_opera = {}

with tqdm(all_opera_items, desc="Extraction entre titres", unit="œuvre") as pbar:
    for i, item in enumerate(pbar):
        # On détermine l'œuvre suivante pour marquer la limite d'arrêt
        next_item = all_opera_items[i+1] if i + 1 < len(all_opera_items) else None
        
        texte = find_operaTexte(item, next_item)
        segment_text_by_opera[item['key']] = texte
        
        pbar.set_postfix(page=item['page'], cat=item['cat'])

# -- EXPORT --
with open('file.json', 'w', encoding='utf-8') as file:
     json.dump(segment_text_by_opera, file, ensure_ascii=False, indent=4)

print("\nExtraction terminée avec succès !")