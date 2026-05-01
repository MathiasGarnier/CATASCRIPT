import re
import gudhi
import manuscripts
import numpy as np
import pandas as pd
import networkx as nx 
from rapidfuzz import fuzz
from scipy.linalg import eigh
import matplotlib.pyplot as plt
from pyvis.network import Network
from networkx.algorithms import bipartite
from matplotlib.animation import FuncAnimation
from sklearn.manifold import SpectralEmbedding
from sklearn.cluster import SpectralClustering

# Lasciate ogni speranza, voi che'ntrate

# À vos risques et périls

#################################################################################
#################################################################################
# On condense ici quelques petites expérimentations
# une grosse partie a été vibe codée afin de savoir si c'était réalisable
# lors de la production des codes finaux, tout sera revu au crible
# et fait à la main; l'idée n'était ici que de savoir si c'était réalisable
# ou pas; + j'avais déjà quelques uns de ses codes dans d'autres langages (Julia)
# et flemme de tout refaire de zéro juste pour tester une petite hypothèse
#################################################################################
#################################################################################

def get_clean_mss_id(mss_str):
    if not mss_str: return "Inconnu"
    # On coupe avant 'ff.' ou 'f.' ou 'f ' pour ne garder que la cote
    # Exemple: "Arundel 409. ff. 54-77" -> "Arundel 409"
    clean = re.split(r'\s+\.?f{1,2}\.', mss_str)[0]
    return clean.strip('. ')

def gen_catalog():
    all_records = []
    for category, manuscripts_list in manuscripts.CORRESPONDENCE_OPERA_CORRECTED_MSS.items():
        for record in manuscripts_list:
            record_with_category = record.copy()
            record_with_category['category'] = category
            all_records.append(record_with_category)
    return pd.DataFrame(all_records)

def gen_catalog_mss_id():
    # Transformation du dictionnaire en DataFrame
    all_data = []
    for category, items in manuscripts.CORRESPONDENCE_OPERA_CORRECTED_MSS.items():
        for item in items:
            new_item = item.copy()
            new_item['category'] = category
            new_item['mss_id'] = get_clean_mss_id(item['mss'])
            all_data.append(new_item)

    return pd.DataFrame(all_data)

def find_similar_strings(string, strings, threshold=90):
    """
        Find strings similar to the given string above the threshold
        use rapidfuzz
    """
    similar = []
    for s in strings:
        ratio = fuzz.ratio(string, s)
        if ratio >= threshold:
            similar.append(s)
    return similar

def agregate_similar_names(df_catalog_vol_1, threshold_=80, DEBUG=True):
    unique_names = df_catalog_vol_1['name'].unique()
    aggregated_names = {}
    processed = set()

    for name in unique_names:
        if name in processed:
            continue
        similar = find_similar_strings(name, unique_names, threshold=threshold_)
        key = min(similar)
        aggregated_names[key] = similar
        processed.update(similar)

    if DEBUG:
        print(f"Aggregated similar names ({len(aggregated_names.items())}):")
        for key, names in aggregated_names.items():
            print(f"{key}: {names}")

    return aggregated_names

def create_aggregated_df(df_catalog_vol_1, aggregated_names):
    """
        Create a mapping from each name to its canonical group namen
    """
    name_to_group = {}
    for canonical_name, similar_names in aggregated_names.items():
        for name in similar_names:
            name_to_group[name] = canonical_name
    
    df_aggregated = df_catalog_vol_1.copy()
    df_aggregated['aggregated_name'] = df_aggregated['name'].map(name_to_group)
    
    return df_aggregated

def create_similarity_graph(aggregated_names):
    """
        Create a graph where vertices are original names and edges connect
        names that belong to the same aggregated class.
        Two names are connected if they belong to the same aggregated group.
    """
    G = nx.Graph()
    
    # Add vertices and edges for each aggregated group
    for canonical_name, similar_names in aggregated_names.items():
        # Add all nodes
        G.add_nodes_from(similar_names)
        
        # Create a complete subgraph (clique) within each aggregated group
        # All names in the same group are connected to each other
        for i, name1 in enumerate(similar_names):
            for name2 in similar_names[i+1:]:
                G.add_edge(name1, name2)
    
    return G

def number_names_wrt_threshold(df_catalog_vol_1, DEBUG=False):
    """
        Plotter le nombre de noms agrégés en fonction du threshold
    """
    x = np.linspace(0, 100, 500)  # From 50 to 100 with step 1
    y = []
    for idx in x:
        lenAgg = len(agregate_similar_names(df_catalog_vol_1, idx, DEBUG=False).items())
        y.append(lenAgg)

    plt.figure(figsize=(10, 6))
    plt.plot(x, y, 'b-', linewidth=2)
    plt.xlabel('Threshold')
    plt.ylabel('Number of Aggregated Name Groups')
    plt.grid(True, alpha=0.3)
    plt.xticks(np.arange(0, 101, 10))
    plt.tight_layout()
    plt.show()

def create_interactive_graph_from_df(df):

    # Gemini pour une visualisation propre.

    net = Network(height="800px", width="100%", bgcolor="#ffffff", font_color="black", select_menu=True)
    net.force_atlas_2based(gravity=-50, central_gravity=0.01, spring_length=100)

    # 1. On crée une liste de groupes uniques pour attribuer des IDs de couleur
    unique_groups = df['aggregated_name'].unique().tolist()
    group_to_id = {name: i for i, name in enumerate(unique_groups)}

    # 2. Ajout des noeuds
    for _, row in df.iterrows():
        net.add_node(
            row['name'], 
            label=row['name'], 
            title=f"Groupe Canonique: {row['aggregated_name']}\nCatégorie: {row['category']}",
            group=group_to_id[row['aggregated_name']], # Pyvis gère les couleurs par ID de groupe
            size=15
        )

    # 3. Ajout des arêtes (Edges)
    for agg_name, group_df in df.groupby('aggregated_name'):
        names_in_cluster = group_df['name'].unique().tolist()
        
        # Si le groupe contient plus d'un élément, on crée la clique
        if len(names_in_cluster) > 1:
            for i, name1 in enumerate(names_in_cluster):
                for name2 in names_in_cluster[i+1:]:
                    net.add_edge(name1, name2, color='lightgray', alpha=0.5)

    # Options d'interface (boutons de contrôle directement dans le HTML)
    net.show_buttons(filter_=['physics']) 
    
    net.show("catalogue_interactif__aggregated_names.html", notebook=False)

def plot_manuscript_reconstruction(df):
    net = Network(height="800px", width="100%", bgcolor="#ffffff", font_color="black", select_menu=True)
    
    # On utilise la physique ForceAtlas2 pour bien séparer les manuscrits "îlots"
    net.force_atlas_2based(gravity=-30, central_gravity=0.005, spring_length=150)

    # 1. Ajouter les noeuds
    unique_works = df['name'].unique()
    for work in unique_works:
        contained_in = df[df['name'] == work]['mss_id'].unique()
        mss_list = " ".join(contained_in)
        
        net.add_node(
            work, 
            label=work, 
            title=f"Présent dans les manuscrits :{mss_list}",
            size=20,
            color="#2ecc71"
        )

    # 2. Créer les liens par manuscrit
    # On groupe par 'mss_id' (le manuscrit physique)
    for mss_id, group in df.groupby('mss_id'):
        works_in_this_ms = group['name'].unique().tolist()
        
        if len(works_in_this_ms) > 1:
            # On relie toutes les oeuvres présentes dans ce manuscrit
            for i, w1 in enumerate(works_in_this_ms):
                for w2 in works_in_this_ms[i+1:]:
                    # L'arête porte le nom du manuscrit commun
                    net.add_edge(w1, w2, title=f"Manuscrit commun : {mss_id}", color="rgba(100,100,100,0.3)")

    net.show_buttons(filter_=['physics'])
    net.show("reconstruction_manuscrits.html", notebook=False)

def spectral_analysis(df):
    # Création du graphe de co-occurrence (comme précédemment)
    G = nx.Graph()
    for mss_id, group in df.groupby('mss_id'):
        works = group['name'].unique().tolist()
        if len(works) > 1:
            for i, w1 in enumerate(works):
                for w2 in works[i+1:]:
                    G.add_edge(w1, w2)
    
    # On travaille sur la plus grande composante connexe
    if not nx.is_connected(G):
        main_comp = max(nx.connected_components(G), key=len)
        G = G.subgraph(main_comp)

    # Calcul du spectre du Laplacien
    L = nx.laplacian_spectrum(G)
    fiedler_value = sorted(L)[1] # La 2ème plus petite valeur
    
    print(f"Valeur de Fiedler : {fiedler_value:.4f}")
    
    if fiedler_value < 0.1:
        print("Interprétation : Le réseau est très 'fissurable'. Il existe des goulots d'étranglement codicologiques.")
    else:
        print("Interprétation : Le réseau est bien intégré, les oeuvres circulent de manière fluide entre les manuscrits.")

    return G, sorted(L)

def plot_spectral_clusters(G):
    # Transformation du graphe en matrice d'adjacence
    adj_matrix = nx.to_numpy_array(G)
    
    # Embedding spectral
    embedding = SpectralEmbedding(n_components=2, affinity='precomputed')
    coords = embedding.fit_transform(adj_matrix)
    
    plt.figure(figsize=(10, 8))
    plt.scatter(coords[:, 0], coords[:, 1], alpha=0.7, c='red')
    
    # Ajouter les labels
    nodes = list(G.nodes())
    for i, txt in enumerate(nodes):
        plt.annotate(txt, (coords[i, 0], coords[i, 1]), fontsize=8)
        
    plt.title("Spectral Embedding : Proximité structurelle des oeuvres")
    plt.grid(True, alpha=0.2)
    plt.show()

def detect_hidden_families(G, n_clusters=4):
    # marche pas?
    adj_matrix = nx.to_numpy_array(G)
    
    sc = SpectralClustering(n_clusters=n_clusters, affinity='precomputed', assign_labels='discretize')
    labels = sc.fit_predict(adj_matrix)
    
    # On range les résultats
    families = {i: [] for i in range(n_clusters)}
    nodes = list(G.nodes())
    for node, label in zip(nodes, labels):
        families[label].append(node)
        
    for label, members in families.items():
        print(f"--- Famille Spectrale {label} ---")
        print(", ".join(members[:5]) + ("..." if len(members)>5 else ""))

def plot_scree_plot(df):
    # 1. Reconstruction du graphe de co-occurrence
    G = nx.Graph()
    for mss_id, group in df.groupby('mss_id'):
        works = group['name'].unique().tolist()
        if len(works) > 1:
            for i, w1 in enumerate(works):
                for w2 in works[i+1:]:
                    G.add_edge(w1, w2)
    
    # 2. Calcul du spectre (valeurs propres) du Laplacien normalisé
    # On trie les valeurs par ordre croissant
    # Les valeurs propres du Laplacien normalisé sont toujours entre 0 et 2
    evals = nx.normalized_laplacian_spectrum(G)
    evals_sorted = np.sort(evals)

    plt.figure(figsize=(10, 6))
    
    # On affiche les 30 premières valeurs pour plus de clarté
    n_show = min(len(evals_sorted), 30)
    plt.plot(range(1, n_show + 1), evals_sorted[:n_show], 'bo-', markersize=8, linewidth=2)

    plt.title("Scree Plot : Analyse spectrale des manuscrits", fontsize=14)
    plt.xlabel("Index de la valeur propre", fontsize=12)
    plt.ylabel("Valeur propre (λ)", fontsize=12)
    plt.xticks(range(1, n_show + 1))
    plt.grid(True, linestyle='--', alpha=0.6)
    
    plt.tight_layout()
    plt.show()

    return evals_sorted

def experiment_fiedler_partition(G):
    # Calcul du vecteur de Fiedler (vecteur propre de la 2ème plus petite valeur propre)
    fiedler_vec = nx.fiedler_vector(G)#nx.fiedler_vector(G, method='lapack')
    
    # On sépare les noeuds selon le signe (positif ou négatif)
    side_a = [node for i, node in enumerate(G.nodes()) if fiedler_vec[i] > 0]
    side_b = [node for i, node in enumerate(G.nodes()) if fiedler_vec[i] <= 0]
    
    print(f"Structure de fracture :")
    print(f" - Bloc A ({len(side_a)} oeuvres) : {side_a[:3]}...")
    print(f" - Bloc B ({len(side_b)} oeuvres) : {side_b[:3]}...")
    
    return fiedler_vec

def animate_diffusion(G, source_node, total_frames=60, max_time=10.0):
    # 1. Préparation des données spectrales pour la performance
    nodes = list(G.nodes())
    if source_node not in nodes:
        print(f"Erreur : {source_node} n'est pas dans le graphe.")
        return

    L = nx.laplacian_matrix(G).toarray()
    # On calcule les valeurs et vecteurs propres : L = U * Lambda * U^T
    evals, evecs = eigh(L)
    
    source_idx = nodes.index(source_node)
    h0 = np.zeros(len(nodes))
    h0[source_idx] = 1.0
    # Projection de la condition initiale dans la base des vecteurs propres
    h0_spectral = evecs.T @ h0

    # 2. Configuration du graphique
    fig, ax = plt.subplots(figsize=(12, 9))
    pos = nx.spring_layout(G, seed=42, k=0.5) # Position fixe pour l'animation
    
    def update(frame):
        ax.clear()
        # Temps logarithmique pour voir la diffusion rapide au début et lente à la fin
        t = (frame / total_frames)**2 * max_time 
        
        # Calcul de h(t) via le spectre : h(t) = U * exp(-t * Lambda) * h0_spectral
        ht = evecs @ (np.exp(-t * evals) * h0_spectral)
        
        # Normalisation pour garder des couleurs vives
        # (La chaleur totale se conserve mais se dilue)
        color_values = ht / (np.max(ht) if np.max(ht) > 0 else 1)
        
        nx.draw_networkx_edges(G, pos, alpha=0.2, ax=ax)
        nodes_plot = nx.draw_networkx_nodes(
            G, pos, 
            node_color=color_values, 
            cmap=plt.cm.YlOrRd, 
            node_size=600, 
            ax=ax
        )
        nx.draw_networkx_labels(G, pos, font_size=7, ax=ax)
        
        ax.set_title(f"Diffusion de l'influence de : {source_node}\nTemps de diffusion t = {t:.2f}")
        ax.axis('off')

    ani = FuncAnimation(fig, update, frames=total_frames, interval=100, repeat=True)
    plt.show()
    return ani

def animate_diffusion_weighted(G, source_node, total_frames=80, max_time=15.0):
    nodes = list(G.nodes())
    if source_node not in nodes:
        print(f"Erreur : {source_node} n'est pas dans le graphe.")
        return

    # 1. Calcul du Laplacien pondéré
    # NetworkX utilise automatiquement l'attribut 'weight' s'il est présent
    L = nx.laplacian_matrix(G, weight='weight').toarray()
    
    # Décomposition spectrale
    evals, evecs = eigh(L)
    
    source_idx = nodes.index(source_node)
    h0 = np.zeros(len(nodes))
    h0[source_idx] = 1.0
    h0_spectral = evecs.T @ h0

    # 2. Préparation du rendu visuel
    fig, ax = plt.subplots(figsize=(14, 10))
    # On calcule les positions une seule fois
    pos = nx.spring_layout(G, weight='weight', seed=42, k=0.6)
    
    # On pré-calcule les largeurs d'arêtes pour la lisibilité
    edge_weights = [G[u][v]['weight'] * 2 for u, v in G.edges()]

    def update(frame):
        ax.clear()
        # Progression du temps (quadratique pour observer la dynamique fine du début)
        t = (frame / total_frames)**2 * max_time 
        
        # Solution de l'équation de la chaleur : h(t) = U * exp(-t * Lambda) * U.T * h(0)
        ht = evecs @ (np.exp(-t * evals) * h0_spectral)
        
        # Normalisation locale pour la couleur (0 à 1)
        max_h = np.max(ht) if np.max(ht) > 0 else 1
        color_values = ht / max_h
        
        # Dessin des arêtes (les plus fortes sont plus visibles)
        nx.draw_networkx_edges(G, pos, alpha=0.15, width=edge_weights, edge_color='gray', ax=ax)
        
        # Dessin des nœuds (la taille peut aussi varier avec l'influence)
        nodes_plot = nx.draw_networkx_nodes(
            G, pos, 
            node_color=color_values, 
            cmap=plt.cm.YlOrRd, 
            node_size=500 + (color_values * 1000), # Les nœuds "chauds" grossissent
            ax=ax
        )
        
        nx.draw_networkx_labels(G, pos, font_size=8, font_weight='bold', ax=ax)
        
        ax.set_title(f"Diffusion pondérée (Newman) de l'influence\nSource : {source_node} | Temps t = {t:.2f}")
        ax.axis('off')

    ani = FuncAnimation(fig, update, frames=total_frames, interval=80, repeat=True)
    plt.show()
    return ani

df_catalog_vol_1 = gen_catalog()
#print(df_catalog_vol_1)

#number_names_wrt_threshold(df_catalog_vol_1)

aggregated_names = agregate_similar_names(df_catalog_vol_1, threshold_=80, DEBUG=True)
df_aggregated = create_aggregated_df(df_catalog_vol_1, aggregated_names)
#print(df_aggregated.head())

#G = create_similarity_graph(aggregated_names)
#plot_similarity_graph(G, aggregated_names)

#create_interactive_graph_from_df(df_aggregated)

df_mss = gen_catalog_mss_id() 

#plot_manuscript_reconstruction(df_mss)

#spectral_analysis(df_mss)

#plot_spectral_clusters(spectral_analysis(df_mss)[0])

#detect_hidden_families(spectral_analysis(df_mss)[0], 10)

# Utilisation
# evals = plot_scree_plot(df_mss)

#experiment_fiedler_partition(spectral_analysis(df_mss)[0])

# G = nx.Graph()
# for mss_id, group in df_mss.groupby('mss_id'):
#     works = group['name'].unique().tolist()
#     if len(works) > 1:
#         for i, w1 in enumerate(works):
#             for w2 in works[i+1:]:
#                 G.add_edge(w1, w2)
# G_main = max((G.subgraph(c).copy() for c in nx.connected_components(G)), key=len)
# animate_diffusion(G_main, "Historia Regum Britanniae")
# C'EST PAS UN AUTODAFE, PROMIS! (équation de la chaleur...)

##########################################################
##########################################################
##########################################################

############## Régler le problème/biais des cliques
# Dans l'approche initiale, si un manuscrit contient les œuvres A, B et C, création d'un triangle (A-B, B-C, A-C). Si un manuscrit massif contient 20 œuvres, génération d'une clique de 190 arêtes.
# Le réseau final sera donc dominé par la structure interne de ce manuscrit géant, noyant complètement les signaux subtils des œuvres transmises par paires dans des petits manuscrits.
# 
# projection de Newman
#
# 1. Initialisation du graphe biparti
B = nx.Graph()

# Séparation des listes de nœuds
manuscrits = df_mss['mss_id'].unique().tolist()
oeuvres = df_mss['name'].unique().tolist()

# Ajout des nœuds avec un attribut 'bipartite' (0 pour manuscrits, 1 pour oeuvres)
# C'est requis par les algorithmes de la bibliothèque bipartite de networkx
B.add_nodes_from(manuscrits, bipartite=0)
B.add_nodes_from(oeuvres, bipartite=1)

# Ajout des arêtes : on relie chaque manuscrit à ses œuvres
for _, row in df_mss.iterrows():
    B.add_edge(row['mss_id'], row['name'])

# 2. Vérification rapide (Optionnel mais recommandé)
if not bipartite.is_bipartite(B):
    print("Attention, le graphe n'est pas strictement biparti !")

# 3. Projection avec la pondération de Newman
# La fonction 'collaboration_weighted_projected_graph' applique exactement la formule 1/(d_k - 1)
G_oeuvres_pondere = bipartite.collaboration_weighted_projected_graph(B, oeuvres)

# 4. Extraction de la composante principale
G_main = max((G_oeuvres_pondere.subgraph(c).copy() for c in nx.connected_components(G_oeuvres_pondere)), key=len)

# print(f"Graphe pondéré créé : {G_main.number_of_nodes()} noeuds et {G_main.number_of_edges()} arêtes.")

# animate_diffusion_weighted(G_main, "Historia Regum Britanniae")



def compute_persistence_romance(G):
    # 1. Préparation de la matrice de distance
    nodes = list(G.nodes())
    n = len(nodes)
    max_dist = 20.0
    dist_matrix = np.full((n, n), np.inf)
    np.fill_diagonal(dist_matrix, 0)
    
    node_to_idx = {node: i for i, node in enumerate(nodes)}
    
    for u, v, data in G.edges(data=True):
        # On transforme le poids de Newman en distance
        # Plus le poids est fort, plus la distance est courte
        weight = data.get('weight', 0.0001)
        dist_matrix[node_to_idx[u]][node_to_idx[v]] = 1.0 / weight
        dist_matrix[node_to_idx[v]][node_to_idx[u]] = 1.0 / weight

    # 2. Création du complexe de Rips
    # On définit une distance max pour limiter les calculs
    try:
        rips_complex = gudhi.RipsComplex(distance_matrix=dist_matrix, max_edge_distance=max_dist)
    except TypeError:
        # Version alternative pour les anciennes/certaines versions de GUDHI
        rips_complex = gudhi.RipsComplex(distance_matrix=dist_matrix)    
        
    simplex_tree = rips_complex.create_simplex_tree(max_dimension=2)

    # 3. Calcul de la persistance
    persistence = simplex_tree.persistence()

    # 4. Visualisation
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    
    # Barcode : chaque barre est une caractéristique topologique
    gudhi.plot_persistence_barcode(persistence, axes=ax1)
    ax1.set_title("Barcode de Persistance (Stabilité des thèmes)")
    
    # Diagramme de persistance : points loin de la diagonale = structures réelles
    gudhi.plot_persistence_diagram(persistence, axes=ax2)
    ax2.set_title("Diagramme de Persistance (beta_0 et beta_1)")
    
    plt.show()
    return simplex_tree, nodes

# Utilisation sur votre graphe pondéré Newman
st, nodes = compute_persistence_romance(G_main)
# Les barres de dimension 0 ($\beta_0$) : Elles partent toutes de 0. Celles qui meurent vite représentent des œuvres qui rejoignent rapidement un groupe. Celles qui survivent longtemps sont des œuvres "isolées" ou des chefs de file de clusters très distincts.
# Les barres de dimension 1 ($\beta_1$) : Ce sont les cycles. Si une barre bleue est longue, elle représente une véritable lacune structurelle. Dans votre catalogue de romances, cela pourrait signifier qu'il y a un vide thématique ou une absence de manuscrits faisant le pont entre trois pôles littéraires pourtant proches.

def extract_topological_cycle(simplex_tree, nodes):
    # 1. On récupère les intervalles de dimension 1 (les cycles)
    pers_dim1 = simplex_tree.persistence_intervals_in_dimension(1)
    
    if len(pers_dim1) == 0:
        print("Aucun cycle beta_1 détecté.")
        return None

    # 2. On trouve l'intervalle avec la plus grande persistance (mort - naissance)
    # On évite les cycles infinis (mort == inf) pour plus de stabilité
    finite_pers = [(i, p[1] - p[0]) for i, p in enumerate(pers_dim1) if p[1] != float('inf')]
    if not finite_pers:
        return None
        
    idx_max, max_p = max(finite_pers, key=lambda x: x[1])
    birth, death = pers_dim1[idx_max]

    print(f"Cycle le plus persistant détecté (Persistance: {max_p:.4f})")
    print(f"Naît à la distance {birth:.4f} et meurt à {death:.4f}")

    # 3. Extraction des arêtes présentes à la naissance du cycle
    # On filtre les simplexes de dimension 1 (arêtes) dont la valeur de filtration 
    # est inférieure ou égale à la date de naissance du cycle.
    cycle_edges = []
    for simplex, filtration in simplex_tree.get_filtration():
        if len(simplex) == 2 and filtration <= birth:
            u, v = nodes[simplex[0]], nodes[simplex[1]]
            cycle_edges.append((u, v))
            
    return cycle_edges, max_p

# Utilisation :
edges, persistence_val = extract_topological_cycle(st, nodes)

def animate_diffusion_with_topology(G, source_node, cycle_edges, total_frames=100, max_time=20.0):
    nodes = list(G.nodes())
    if source_node not in nodes:
        print(f"Erreur : {source_node} n'est pas dans le graphe.")
        return

    # 1. Calcul spectral (Laplacien pondéré Newman)
    L = nx.laplacian_matrix(G, weight='weight').toarray()
    evals, evecs = eigh(L)
    
    source_idx = nodes.index(source_node)
    h0 = np.zeros(len(nodes))
    h0[source_idx] = 1.0
    h0_spectral = evecs.T @ h0

    # 2. Préparation du graphique
    fig, ax = plt.subplots(figsize=(14, 10), facecolor='#111111') # Fond sombre pour l'effet néon
    pos = nx.spring_layout(G, weight='weight', seed=42, k=0.5)
    
    # Séparation des arêtes pour le dessin
    all_edges = list(G.edges())
    # On s'assure que les arêtes du cycle sont bien présentes dans le graphe
    valid_cycle_edges = [e for e in cycle_edges if G.has_edge(*e)]

    def update(frame):
        ax.clear()
        ax.set_facecolor('#111111')
        
        # Temps logarithmique/quadratique
        t = (frame / total_frames)**1.5 * max_time 
        ht = evecs @ (np.exp(-t * evals) * h0_spectral)
        
        # Normalisation des couleurs
        color_values = ht / (np.max(ht) if np.max(ht) > 0 else 1)
        
        # --- DESSIN ---
        # 1. Arêtes standard (fond discret)
        nx.draw_networkx_edges(G, pos, alpha=0.1, edge_color='gray', width=1, ax=ax)
        
        # 2. LE CYCLE TOPOLOGIQUE (Effet Néon Cyan)
        nx.draw_networkx_edges(
            G, pos, 
            edgelist=valid_cycle_edges, 
            edge_color='#00f2ff', # Cyan néon
            width=3, 
            alpha=0.8,
            ax=ax
        )
        
        # 3. Nœuds (Influence)
        nodes_plot = nx.draw_networkx_nodes(
            G, pos, 
            node_color=color_values, 
            cmap=plt.cm.YlOrRd, 
            node_size=400 + (color_values * 1200),
            ax=ax
        )
        
        # Labels (uniquement pour les nœuds importants ou le cycle pour éviter l'encombrement)
        important_nodes = {n: n for n in nodes if ht[nodes.index(n)] > 0.1}
        nx.draw_networkx_labels(G, pos, labels=important_nodes, font_size=7, font_color='white', ax=ax)
        
        ax.set_title(f"Propagation de l'influence vs Vide Topologique\nTemps t = {t:.2f}", color='white', fontsize=14)
        ax.axis('off')

    ani = FuncAnimation(fig, update, frames=total_frames, interval=60, repeat=True)
    plt.show()
    return ani

# Appel :
#animate_diffusion_with_topology(G_main, "Historia Regum Britanniae", edges)
#L'effet de contournement : Si le cycle (en bleu néon) entoure un groupe de nœuds qui restent "froids" (jaunes/blancs) pendant longtemps malgré leur proximité géométrique, vous avez identifié un point de rupture de la tradition.
#La vitesse de franchissement : Observez comment la "chaleur" traverse les arêtes du cycle. Si elle passe rapidement par un côté mais pas par l'autre, cela signifie que la boucle topologique est asymétrique : une œuvre fait le pont, tandis que l'autre est un cul-de-sac.
#La "Source" vs le "Trou" : Si l'Historia Regum Britanniae est elle-même un nœud du cycle, vous verrez comment son influence est littéralement "piégée" ou canalisée par cette structure circulaire.

def generate_topology_report(G, source_node, cycle_edges, evecs, evals, nodes):
    report_data = []
    # On transforme la liste d'arêtes en un ensemble de noms d'œuvres uniques
    nodes_in_cycle = set()
    for u, v in cycle_edges:
        nodes_in_cycle.add(u)
        nodes_in_cycle.add(v)
    
    source_idx = nodes.index(source_node)
    h0 = np.zeros(len(nodes))
    h0[source_idx] = 1.0
    h0_spectral = evecs.T @ h0

    for node in nodes_in_cycle:
        node_idx = nodes.index(node)
        reception_t = 999.0  # On utilise un nombre élevé au lieu d'un string pour le tri
        
        # Simulation du flux
        for t in np.linspace(0, 30, 300):
            # Calcul de l'influence à l'instant t
            ht = evecs @ (np.exp(-t * evals) * h0_spectral)
            
            # .item() ou float() garantit qu'on extrait une valeur simple et non un array
            influence_val = float(ht[node_idx])
            
            if influence_val >= 0.5:
                reception_t = round(t, 2)
                break
        
        # Poids moyen des liens connectés à ce nœud AU SEIN du cycle
            internal_weights = [
                G[node][v].get('weight', 0) 
                for v in G.neighbors(node) 
                if v in nodes_in_cycle
            ]        
            avg_w = np.mean(internal_weights) if internal_weights else 0
        
        report_data.append({
            "Œuvre": node,
            "Temps de Réception (t)": reception_t,
            "Poids Newman Moyen": round(avg_w, 4),
            "Degré Pondéré": round(G.degree(node, weight='weight'), 3)
        })

    # Création du DataFrame
    df_report = pd.DataFrame(report_data)
    
    # Tri numérique (les 999.0 se retrouveront à la fin)
    df_report = df_report.sort_values(by="Temps de Réception (t)")
    
    # Optionnel : On remet un label lisible après le tri pour les textes isolés
    df_report["Temps de Réception (t)"] = df_report["Temps de Réception (t)"].replace(999.0, "> 30 (Isolée)")
    
    return df_report

nodes = list(G_main.nodes())

# B. On calcule le Laplacien pondéré (celui avec les poids de Newman)
L = nx.laplacian_matrix(G_main, weight='weight').toarray()

# C. On extrait les valeurs propres (evals) et vecteurs propres (evecs)
evals, evecs = eigh(L)

# D. On récupère les arêtes du cycle (déjà fait via votre fonction extract_topological_cycle)
# edges, persistence_val = extract_topological_cycle(st, nodes)
cycle_edges = edges
# Exécution
df_final = generate_topology_report(G_main, "Historia Regum Britanniae", cycle_edges, evecs, evals, nodes)
print(df_final)

# Trouver les manuscrits qui contiennent l'Historia ET une autre œuvre du cycle
cycle_nodes = df_final[df_final['Œuvre'] != "Historia Regum Britanniae"]['Œuvre'].tolist()

bridge_mss = df_mss[df_mss['name'] == "Historia Regum Britanniae"]['mss_id'].unique()
potential_bridges = df_mss[(df_mss['mss_id'].isin(bridge_mss)) & (df_mss['name'].isin(cycle_nodes))]

print("Manuscrits faisant le pont entre l'Historia et le cycle :")
print(potential_bridges[['mss_id', 'name']])
# Le paradoxe du collectionneur : Plus un manuscrit est riche et encyclopédique, moins il est efficace pour "propager" une influence thématique spécifique, car il mélange trop de genres différents. Le réseau considère alors ces liens comme "accidentels" plutôt que "structurels".


# D'un point de vue historique, cela revient à dire : "Peu importe que ces volumes soient des encyclopédies massives, nous considérons que le fait d'y avoir mis l'Historia et Alexandre le Grand est un acte éditorial délibéré et fort."
def stress_test_bridges(G, bridge_data, source_node, cycle_edges, evecs, evals, nodes):
    # 1. Création d'une copie du graphe pour ne pas corrompre l'original
    G_stressed = G.copy()
    
    # 2. On identifie les paires (Historia, Autre) présentes dans les manuscrits ponts
    # On force leur poids à 1.0 (suppression de la dilution de Newman)
    for _, row in bridge_data.iterrows():
        target_node = row['name']
        if G_stressed.has_edge(source_node, target_node):
            G_stressed[source_node][target_node]['weight'] = 1.5 # On "booste" le lien
            print(f"Boost appliqué : {source_node} <---> {target_node}")

    # 3. Recalcul du spectre sur le graphe "stressé"
    L_stressed = nx.laplacian_matrix(G_stressed, weight='weight').toarray()
    evals_s, evecs_s = eigh(L_stressed)
    
    # 4. Génération du nouveau rapport
    return generate_topology_report(G_stressed, source_node, cycle_edges, evecs_s, evals_s, nodes)

# Exécution du test
df_stressed = stress_test_bridges(G_main, potential_bridges, "Historia Regum Britanniae", cycle_edges, evecs, evals, nodes)

print("\n--- RAPPORT APRÈS LEVÉE DES BARRIÈRES (STRESS TEST) ---")
print(df_stressed)

def plot_stress_test_comparison(G_orig, G_stressed, source_node, cycle_edges):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8), facecolor='#f4f4f4')
    pos = nx.spring_layout(G_orig, seed=42)
    
    # Configuration commune
    node_colors_orig = ['red' if n == source_node else 'lightblue' for n in G_orig.nodes()]
    cycle_nodes = set([n for e in cycle_edges for n in e])
    
    # Graphe 1 : État Naturel (Dilution de Newman)
    nx.draw_networkx_edges(G_orig, pos, alpha=0.2, ax=ax1)
    nx.draw_networkx_nodes(G_orig, pos, node_color=node_colors_orig, 
                           node_size=[500 if n in cycle_nodes else 100 for n in G_orig.nodes()], ax=ax1)
    ax1.set_title("1. État Naturel : Fragmentation des Traditions\n(L'Historia est isolée par la dilution)", fontsize=14)

    # Graphe 2 : Stress Test (Levée des barrières)
    nx.draw_networkx_edges(G_stressed, pos, alpha=0.2, ax=ax2)
    # On met en gras les ponts boostés
    boosted_edges = [(source_node, n) for n in cycle_nodes if G_stressed.has_edge(source_node, n)]
    nx.draw_networkx_edges(G_stressed, pos, edgelist=boosted_edges, width=3, edge_color='orange', ax=ax2)
    nx.draw_networkx_nodes(G_stressed, pos, node_color=node_colors_orig, 
                           node_size=[500 if n in cycle_nodes else 100 for n in G_stressed.nodes()], ax=ax2)
    ax2.set_title("2. Stress Test : Résistance Topologique\n(Malgré les ponts orange, le flux ne passe pas)", fontsize=14)

    plt.tight_layout()
    plt.show()

# 1. Copie profonde du graphe original
G_stressed = G_main.copy()

# 2. On définit nos cibles (les œuvres du cycle)
cycle_nodes = set([n for edge in edges for n in edge])

# 3. On booste les arêtes entre l'Historia et ces œuvres
source = "Prophecies of Merlin"
for target in cycle_nodes:
    if G_stressed.has_edge(source, target):
        # On force un poids très élevé (1.5) pour annuler l'effet de dilution
        G_stressed[source][target]['weight'] = 1.5
        print(f"Lien boosté : {source} <---> {target}")

# 4. Recalcul spectral pour le rapport et l'animation si besoin
import scipy.linalg as la
L_stressed = nx.laplacian_matrix(G_stressed, weight='weight').toarray()
evals_s, evecs_s = la.eigh(L_stressed)

plot_stress_test_comparison(G_main, G_stressed, "Prophecies of Merlin", cycle_edges) # soucis avec cycle_edges
# pas de la persistance mais de la résistance topologique
# Nous avons d'abord modélisé le catalogue comme un graphe biparti (manuscrits-œuvres) projeté via la pondération de Newman, qui pénalise la proximité fortuite dans les grandes compilations. Nous avons ensuite utilisé l'homologie persistante (GUDHI) pour détecter un cycle $\beta_1$ (une boucle de transmission entre romances, sagas et chroniques). Enfin, nous avons testé la perméabilité de ce cycle par une diffusion spectrale (Laplacien), d'abord en conditions réelles, puis lors d'un stress-test en supprimant artificiellement la dilution de Newman pour les manuscrits "ponts" (ex: Nero D. viii).
# Le résultat est sans appel : même en forçant la connectivité des ponts physiques, l'influence de l'Historia Regum Britanniae reste bloquée ($t > 30$). Cela démontre que la proximité matérielle (être dans le même livre) ne signifie pas une parenté organique.
# Le cycle détecté par la topologie est une "cohabitation de archives" : ces œuvres (Alexander, Turpin, Magus Saga) partagent des espaces de stockage communs sans jamais fusionner thématiquement. En mathématiques, cela s'appelle une rupture de conductivité spectrale. Pour l'historien, c'est la preuve que les copistes médiévaux utilisaient ces manuscrits comme des "vases d'expansion" pour stocker des textes disparates, créant ainsi une illusion de structure circulaire que seule l'analyse par diffusion permet de débusquer.
# à vérifier......