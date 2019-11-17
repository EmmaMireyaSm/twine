"""Module containing logic for handling settings."""
# Copyright 2018 Ian Stapleton Cordasco
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from typing import cast, Optional

import argparse

from twine import exceptions
from twine import repository
from twine import utils
from twine import auth
from twine import types


class Settings:
    """Object that manages the configuration for Twine.

    This object can only be instantiated with keyword arguments.

    For example,

    .. code-block:: python

        Settings(True, username='fakeusername')

    Will raise a :class:`TypeError`. Instead, you would want

    .. code-block:: python

        Settings(sign=True, username='fakeusername')
    """

    def __init__(
        self,
        *,
        sign: bool = False,
        sign_with: Optional[str] = 'gpg',
        identity: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        non_interactive: bool = False,
        comment: Optional[str] = None,
        config_file: str = '~/.pypirc',
        skip_existing: bool = False,
        cacert: Optional[str] = None,
        client_cert: Optional[str] = None,
        repository_name: str = 'pypi',
        repository_url: Optional[str] = None,
        verbose: bool = False,
        disable_progress_bar: bool = False,
        **ignored_kwargs
    ) -> None:
        """Initialize our settings instance.

        :param bool sign:
            Configure whether the package file should be signed.

            This defaults to ``False``.
        :param str sign_with:
            The name of the executable used to sign the package with.

            This defaults to ``gpg``.
        :param str identity:
            The GPG identity that should be used to sign the package file.
        :param str username:
            The username used to authenticate to the repository (package
            index).
        :param str password:
            The password used to authenticate to the repository (package
            index).
        :param bool non_interactive:
            Do not interactively prompt for username/password if the required
            credentials are missing.

            This defaults to ``False``.
        :param str comment:
            The comment to include with each distribution file.
        :param str config_file:
            The path to the configuration file to use.

            This defaults to ``~/.pypirc``.
        :param bool skip_existing:
            Specify whether twine should continue uploading files if one
            of them already exists. This primarily supports PyPI. Other
            package indexes may not be supported.

            This defaults to ``False``.
        :param str cacert:
            The path to the bundle of certificates used to verify the TLS
            connection to the package index.
        :param str client_cert:
            The path to the client certificate used to perform authentication
            to the index.

            This must be a single file that contains both the private key and
            the PEM-encoded certificate.
        :param str repository_name:
            The name of the repository (package index) to interact with. This
            should correspond to a section in the config file.
        :param str repository_url:
            The URL of the repository (package index) to interact with. This
            will override the settings inferred from ``repository_name``.
        :param bool verbose:
            Show verbose output.
        :param bool disable_progress_bar:
            Disable the progress bar.

            This defaults to ``False``
        """
        self.config_file = config_file
        self.comment = comment
        self.verbose = verbose
        self.disable_progress_bar = disable_progress_bar
        self.skip_existing = skip_existing
        self._handle_repository_options(
            repository_name=repository_name, repository_url=repository_url,
        )
        self._handle_package_signing(
            sign=sign, sign_with=sign_with, identity=identity,
        )
        # _handle_certificates relies on the parsed repository config
        self._handle_certificates(cacert, client_cert)
        creds = types.CredentialInput(username, password)
        self.auth = auth.Resolver.choose(not non_interactive)(self, creds)

    @property
    def username(self):
        return self.auth.username

    @property
    def password(self):
        return self.auth.password

    @property
    def system(self):
        return self.repository_config['repository']

    @staticmethod
    def register_argparse_arguments(parser: argparse.ArgumentParser) -> None:
        """Register the arguments for argparse."""
        parser.add_argument(
            "-r", "--repository",
            action=utils.EnvironmentDefault,
            env="TWINE_REPOSITORY",
            default="pypi",
            help="The repository (package index) to upload the package to. "
                 "Should be a section in the config file (default: "
                 "%(default)s). (Can also be set via %(env)s environment "
                 "variable.)",
        )
        parser.add_argument(
            "--repository-url",
            action=utils.EnvironmentDefault,
            env="TWINE_REPOSITORY_URL",
            default=None,
            required=False,
            help="The repository (package index) URL to upload the package to."
                 " This overrides --repository. "
                 "(Can also be set via %(env)s environment variable.)"
        )
        parser.add_argument(
            "-s", "--sign",
            action="store_true",
            default=False,
            help="Sign files to upload using GPG.",
        )
        parser.add_argument(
            "--sign-with",
            default="gpg",
            help="GPG program used to sign uploads (default: %(default)s).",
        )
        parser.add_argument(
            "-i", "--identity",
            help="GPG identity used to sign files.",
        )
        parser.add_argument(
            "-u", "--username",
            action=utils.EnvironmentDefault,
            env="TWINE_USERNAME",
            required=False,
            help="The username to authenticate to the repository "
                 "(package index) as. (Can also be set via "
                 "%(env)s environment variable.)",
        )
        parser.add_argument(
            "-p", "--password",
            action=utils.EnvironmentDefault,
            env="TWINE_PASSWORD",
            required=False,
            help="The password to authenticate to the repository "
                 "(package index) with. (Can also be set via "
                 "%(env)s environment variable.)",
        )
        parser.add_argument(
            "--non-interactive",
            action="store_true",
            default=False,
            required=False,
            help="Do not interactively prompt for username/password if the "
                 "required credentials are missing."
        )
        parser.add_argument(
            "-c", "--comment",
            help="The comment to include with the distribution file.",
        )
        parser.add_argument(
            "--config-file",
            default="~/.pypirc",
            help="The .pypirc config file to use.",
        )
        parser.add_argument(
            "--skip-existing",
            default=False,
            action="store_true",
            help="Continue uploading files if one already exists. (Only valid "
                 "when uploading to PyPI. Other implementations may not "
                 "support this.)",
        )
        parser.add_argument(
            "--cert",
            action=utils.EnvironmentDefault,
            env="TWINE_CERT",
            default=None,
            required=False,
            metavar="path",
            help="Path to alternate CA bundle (can also be set via %(env)s "
                 "environment variable).",
        )
        parser.add_argument(
            "--client-cert",
            metavar="path",
            help="Path to SSL client certificate, a single file containing the"
                 " private key and the certificate in PEM format.",
        )
        parser.add_argument(
            "--verbose",
            default=False,
            required=False,
            action="store_true",
            help="Show verbose output."
        )
        parser.add_argument(
            "--disable-progress-bar",
            default=False,
            required=False,
            action="store_true",
            help="Disable the progress bar."
        )

    @classmethod
    def from_argparse(cls, args: argparse.Namespace) -> "Settings":
        """Generate the Settings from parsed arguments."""
        settings = vars(args)
        settings['repository_name'] = settings.pop('repository')
        settings['cacert'] = settings.pop('cert')
        return cls(**settings)

    def _handle_package_signing(
        self,
        sign: bool,
        sign_with: Optional[str],
        identity: Optional[str]
    ) -> None:
        if not sign and identity:
            raise exceptions.InvalidSigningConfiguration(
                "sign must be given along with identity"
            )
        self.sign = sign
        self.sign_with = sign_with
        self.identity = identity

    def _handle_repository_options(
        self,
        repository_name: str,
        repository_url: Optional[str]
    ) -> None:
        self.repository_config = utils.get_repository_from_config(
            self.config_file,
            repository_name,
            repository_url,
        )
        self.repository_config['repository'] = utils.normalize_repository_url(
            cast(str, self.repository_config['repository']),
        )

    def _handle_certificates(
        self,
        cacert: Optional[str],
        client_cert: Optional[str]
    ) -> None:
        self.cacert = utils.get_cacert(cacert, self.repository_config)
        self.client_cert = utils.get_clientcert(
            client_cert,
            self.repository_config,
        )

    def check_repository_url(self) -> None:
        """Verify we are not using legacy PyPI.

        :raises:
            :class:`~twine.exceptions.UploadToDeprecatedPyPIDetected`
        """
        repository_url = cast(str, self.repository_config['repository'])

        if repository_url.startswith((repository.LEGACY_PYPI,
                                      repository.LEGACY_TEST_PYPI)):
            raise exceptions.UploadToDeprecatedPyPIDetected.from_args(
                repository_url,
                utils.DEFAULT_REPOSITORY,
                utils.TEST_REPOSITORY
            )

    def create_repository(self) -> repository.Repository:
        """Create a new repository for uploading."""
        repo = repository.Repository(
            cast(str, self.repository_config['repository']),
            self.username,
            self.password,
            self.disable_progress_bar,
        )
        repo.set_certificate_authority(self.cacert)
        repo.set_client_certificate(self.client_cert)
        return repo
