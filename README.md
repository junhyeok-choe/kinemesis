# kinemesis

> **Status: pre-alpha. The API, file format and command line are unstable and will change without notice.** The M1 slice (rig FK, keyframes, SVG) exists; IK, bend/arc segments, raster output and interchange are not built yet. Name confirmed by the maintainer on 2026-10-29: **kinemesis** (kinema + mimesis). Intended package names: distribution `kinemesis`, import `kinemesis`, CLI `kinemesis` (nothing is published to PyPI yet).

Kinemesis (κίνημα + μίμησις) — μια ανεξάρτητη μηχανή 2D κίνησης για αρθρωτές φιγούρες: καθαρή, ντετερμινιστική και ελεύθερη, ώστε κάθε στιγμή της κίνησης να μπορεί να υπολογιστεί, να ελεγχθεί και να αναπαραχθεί.

*(Draft Greek text, needs review by a native speaker. English: an independent 2D animation engine for articulated figures — clean, deterministic and free — so that every instant of motion can be computed, verified and reproduced.)*

## What this will be

A standalone, Python-native 2D animation engine: articulated figures and rigs, forward/inverse kinematics, keyframes and easing, deterministic evaluation at any time, headless rendering, a Python API and CLI, and a versioned, editable project format. Manim Community support is planned as an **optional, separate adapter**; the engine must never depend on Manim, a GUI, or an MCP server.

Name: *kinema* (κίνημα, movement; root of both "kinematics" and "cinema") + *mimesis* (μίμησις, imitation/representation) — faithful, deterministic reproduction of motion.

Loose backronym (in the spirit of acronyms like GEDI, letters need not all map to words): **KIN**ematic **E**ngine for **M**otion **E**valuation, **S**keletons and **I**nterchange of **S**cenes.
