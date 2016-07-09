import os
import sys

from recommonmark.transform import AutoStructify

sys.path.insert(0, os.path.dirname(os.path.abspath('..')))


from tg_option_container import VERSION  # NOQA


on_rtd = os.environ.get('READTHEDOCS', None) == 'True'

# -- General configuration ------------------------------------------------
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
]
templates_path = ['_templates']
source_parsers = {
    '.md': 'recommonmark.parser.CommonMarkParser',
}
source_suffix = ['.md', '.rst']
master_doc = 'index'

# General information about the project.
project = u'tg-option-container'
copyright = u'2016, Thorgate'
author = u'Thorgate'
version = VERSION
release = VERSION
exclude_patterns = []
pygments_style = 'sphinx'
todo_include_todos = False
github_doc_root = 'https://github.com/thorgate/tg-option-container/tree/master/docs/'


def setup(app):
    app.add_config_value('recommonmark_config', {
        'enable_eval_rst': True,
        'url_resolver': lambda url: github_doc_root + url,
        'auto_toc_tree_section': 'Contents',
    }, True)

    app.add_transform(AutoStructify)



if not on_rtd:
    import sphinx_rtd_theme

    html_theme = 'sphinx_rtd_theme'
    html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]
