This folder is the published site. GitHub Pages serves it from `main` / `docs`.

  index.html   the page, hand-written, no build step and no framework
  data.json    everything it shows, written by `python src/build_site.py`

The split is the point. The pipeline produces the numbers and the page consumes
them, so a new quarter means rerunning the pipeline and committing one file.
