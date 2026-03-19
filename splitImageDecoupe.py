import cv2
import numpy as np
"""découper une image en stickers complexes comme ceux de votre image est un défi intéressant qui nécessite plusieurs étapes et outils. Voici une approche utilisant Python, ainsi qu'un script exemple pour vous guider.
L'approche pour créer vos stickers complexes

Pour automatiser la création de stickers avec texte et photo, nous devons suivre ces étapes :

    Détection d'objets (Facultatif mais utile) : Si vos stickers sont mélangés ou de tailles variées, nous pouvons utiliser un modèle de détection d'objets pour identifier les zones probables de chaque sticker. Cela simplifie les étapes suivantes.

    Détection des contours : C'est l'étape la plus cruciale. Nous utilisons l'algorithme de Canny pour trouver les contours de tous les éléments à l'intérieur de l'image.

    Filtrage et sélection : La détection de contours va générer beaucoup de "bruit" (petites lignes, textures). Nous devons filtrer ces résultats pour ne conserver que les contours les plus grands, qui représentent probablement les stickers eux-mêmes.

    Découpe et redressement (Facultatif) : Pour chaque grand contour, nous découpons la zone correspondante. Si le sticker est incliné, nous pouvons utiliser des techniques de redressement pour le remettre droit.

    Création du masque de sticker : Pour chaque zone découpée, nous créons un masque (une image en noir et blanc) où le sticker est en blanc et le fond est en noir. Ce masque nous sert à donner sa forme au sticker final.

    Ajout de transparence (Canal Alpha) : C'est ici que la "magie" opère. Nous utilisons le masque pour ajouter une quatrième couche (le canal alpha) à l'image du sticker. Cette couche définit la transparence : là où le masque est blanc, le sticker est opaque ; là où le masque est noir, le sticker est transparent.
"""
def creer_stickers(image_path, output_dir):
    """
    Crée des stickers avec fond transparent à partir d'une image.
    """
    # 1. Charger l'image
    image = cv2.imread(image_path)
    if image is None:
        print(f"Erreur : Impossible de charger l'image {image_path}")
        return

    # Convertir en niveaux de gris pour faciliter le traitement
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 2. Détection des contours avec Canny
    # Ajustez les seuils si nécessaire pour votre image spécifique
    edges = cv2.Canny(gray, threshold1=30, threshold2=100)

    # 3. Trouver les contours
    # cv2.RETR_EXTERNAL pour ne garder que les contours extérieurs (les stickers)
    # cv2.CHAIN_APPROX_SIMPLE pour simplifier les contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    print(f"{len(contours)} contours potentiels trouvés.")

    # Créer le dossier de sortie si nécessaire
    import os
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 4. Traiter chaque contour
    sticker_count = 0
    for i, contour in enumerate(contours):
        # 5. Filtrage des contours par aire
        # Définissez une aire minimale pour ignorer le bruit
        area = cv2.contourArea(contour)
        if area < 5000: # Exemple de seuil, à ajuster selon vos stickers
            continue

        sticker_count += 1
        print(f"Traitement du sticker {sticker_count} (Aire: {area})...")

        # Trouver le rectangle englobant pour découper la zone
        x, y, w, h = cv2.boundingRect(contour)
        sticker_roi = image[y:y+h, x:x+w]

        # 6. Création du masque de sticker
        # Créer une image noire de la même taille que la zone découpée
        mask = np.zeros((h, w), dtype=np.uint8)
        # Ajuster le contour pour qu'il soit relatif à la zone découpée
        adjusted_contour = contour - (x, y)
        # Remplir le contour en blanc dans le masque
        cv2.drawContours(mask, [adjusted_contour], -1, 255, thickness=cv2.FILLED)

        # 7. Ajouter le canal alpha (transparence)
        # Créer une image avec 4 canaux (BGRA)
        sticker_bgra = cv2.cvtColor(sticker_roi, cv2.COLOR_BGR2BGRA)
        # Utiliser le masque comme canal alpha
        sticker_bgra[:, :, 3] = mask

        # Sauvegarder le sticker
        output_path = os.path.join(output_dir, f"sticker_{sticker_count}.png")
        cv2.imwrite(output_path, sticker_bgra)
        print(f"Sticker {sticker_count} sauvegardé : {output_path}")

    print(f"Traitement terminé. {sticker_count} stickers créés dans {output_dir}")
# --- Exemple d'utilisation ---
# Spécifiez le chemin vers votre image et le dossier de sortie
image_path = "assets/image.png" # Assurez-vous d'avoir l'image dans le même dossier
output_dir = 'output_stickers'

creer_stickers(image_path, output_dir)