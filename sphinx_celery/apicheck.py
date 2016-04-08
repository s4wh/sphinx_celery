"""

Sphinx Autodoc coverage checker.
================================

This builder extension makes sure all modules in the documented
package is represented in the autodoc API reference.

Usage
-----

.. code-block:: console

    $ sphinx-build -b apicheck -d _build/doctrees . _build/apicheck

Configuration
-------------

apicheck_ignore_modules
~~~~~~~~~~~~~~~~~~~~~~~

List of modules to ignore, either as module names or regexes.

Example:

.. code-block:: python

    apicheck_ignore_modules = [
        'django.utils.functional',
        r'django.db.*',
    ]

Test packages are ignored by default, even if this setting is defined.

apicheck_package
~~~~~~~~~~~~~~~~

The package to verify, can be the fully-qualified name of a module
or an actual module.

Example:

.. code-block:: python

    apicheck_package = 'django'

Default is the value of the ``project`` configuration key in all lowercase.


apicheck_domains
~~~~~~~~~~~~~~~~

List of domains to check.

Default is ``['py']`` and Python is the only domain currently supported.

"""
from __future__ import absolute_import, unicode_literals

import importlib
import os
import pickle
import re

from collections import defaultdict
from six import string_types

from sphinx.builders import Builder
from sphinx.util.console import bold, darkgreen, green, red

from .utils import bytes_if_py2

DEFAULT_IGNORE = [r'.*?\.tests.*']

TITLEHEADER = '='
SUBHEADER = '-'

ERR_MISSING = 'Undocumented Autodoc Modules'
ERR_INVALID_REGEX = 'Invalid regex {0!r} in apicheck_ignore_modules: {1!r}'

OK_STATUS = 'OK: All modules documented :o)'

NOK_STATUS = """
{title}

{undocumented}\
"""

DOMAIN_FORMAT = """\
{domain}

{modules}
"""

MODULE_FORMAT = '- {module}'


def title(s, spacing=2, sep=TITLEHEADER):
    return '\n'.join([
        sep * (len(s) + spacing),
        '{0}{1}{0}'.format(' ' * (spacing // 2), red(s)),
        sep * (len(s) + spacing),
    ])


def header(s, sep=SUBHEADER):
    return '\n'.join([bold(s), sep * len(s)])


def find_python_modules(package):
    if isinstance(package, string_types):
        package = importlib.import_module(package)
    name, path = package.__name__, package.__file__
    current_dist_depth = len(name.split('.')) - 1
    current_dist = os.path.join(os.path.dirname(path),
                                *([os.pardir] * current_dist_depth))
    abs = os.path.abspath(current_dist)
    dist_name = os.path.basename(abs)

    for dirpath, dirnames, filenames in os.walk(abs):
        package = (dist_name + dirpath[len(abs):]).replace('/', '.')
        if '__init__.py' in filenames:
            yield package
            for filename in filenames:
                if filename.endswith('.py') and filename != '__init__.py':
                    yield '.'.join([package, filename])[:-3]


class APICheckBuilder(Builder):

    name = 'apicheck'

    find_modules = {
        'py': find_python_modules,
    }

    def init(self):
        self.ignore_patterns = self.compile_regexes(
            self.config.apicheck_ignore_modules + DEFAULT_IGNORE,
        )
        self.check_domains = self.config.apicheck_domains
        self.check_package = (
            self.config.apicheck_package or self.config.project.lower())

        self.undocumented = defaultdict(list)

    def compile_regex(self, regex):
        if not regex.startswith('^'):
            regex = '^{0}'.format(regex)
        if not regex.endswith('$'):
            regex = '{0}$'.format(regex)
        try:
            return re.compile(regex)
        except Exception as exc:
            self.warn(ERR_INVALID_REGEX.format(regex, exc))

    def compile_regexes(self, regexes):
        return [self.compile_regex(regex) for regex in regexes]

    def get_outdated_docs(self):
        return 'apicheck overview'

    def is_ignored_module(self, module):
        return any(regex.match(module) for regex in self.ignore_patterns)

    def write(self, *ignored):
        for domain in self.check_domains:
            self.build_coverage(domain)
        self.write_coverage(self.check_domains)

    def build_coverage(self, domain):
        self.undocumented[domain].extend(self.find_undocumented(
            self.check_package, domain, self.env.domaindata[domain]['modules'],
        ))

    def find_undocumented(self, package, domain, documented):
        return (
            mod for mod in self.find_modules[domain](package)
            if mod not in documented and not self.is_ignored_module(mod)
        )

    def write_coverage(self, domains):
        status = any(self.undocumented.values())
        if status:
            self.app.statuscode = 2
            print(self.format_undocumented_domains(domains))
        else:
            print(green(OK_STATUS))

    def format_undocumented_domains(self, domains):
        return NOK_STATUS.format(
            title=title(ERR_MISSING),
            undocumented='\n'.join(
                self.format_undocumented_domain(domain) for domain in domains
            ),
        )

    def format_undocumented_domain(self, domain):
        return DOMAIN_FORMAT.format(domain=header(domain), modules='\n'.join(
            self.format_undocumented_module(module)
            for module in self.undocumented[domain]
        ))

    def format_undocumented_module(self, module):
        return MODULE_FORMAT.format(module=darkgreen(module))

    def as_dict(self):
        return {
            'undocumented': dict(self.undocumented),
        }

    def finish(self):
        picklepath = os.path.join(self.outdir, 'apicheck.pickle')
        with open(picklepath, mode='wb') as fh:
            pickle.dump(self.as_dict(), fh)


def setup(app):
    app.add_builder(APICheckBuilder)
    app.add_config_value(
        bytes_if_py2('apicheck_ignore_modules'), [".*?\.tests.*"], False)
    app.add_config_value(
        bytes_if_py2('apicheck_domains'), ['py'], False)
    app.add_config_value(
        bytes_if_py2('apicheck_package'), None, False)