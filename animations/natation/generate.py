#!/usr/bin/env python3
"""Génère les animations SVG des éducatifs de natation.

Le nageur est un modèle 3D articulé (voir model.py) : chaque partie du corps
est un volume à sections elliptiques, projeté sous plusieurs angles puis
animé en SMIL. Les SVG produits sont autonomes (aucun script), lisibles dans
un navigateur, une balise <img> ou sur GitHub, et suivent le thème clair/sombre.

Usage :
    pip install shapely
    python3 generate.py            # tous les exercices
    python3 generate.py 02         # seulement ceux dont le nom contient « 02 »
"""

import os
import sys

from exercises import EXERCISES

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def main(filters):
    for ex in EXERCISES:
        if filters and not any(f in ex.slug for f in filters):
            continue
        path = os.path.join(OUT_DIR, ex.slug + ".svg")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(ex.render())
        print("%-40s %7.1f Ko" % (os.path.basename(path), os.path.getsize(path) / 1024))


if __name__ == "__main__":
    main(sys.argv[1:])
