import base64
import logging
import subprocess
import typing
from abc import abstractmethod
from dataclasses import dataclass

import requests

from .auth_client import AuthorizationClient
from .exceptions import AccessTokenNotFoundError, AuthenticationError
from .keyring import Credentials, KeyringStore


@dataclass
class ClientConfig:
    """
    Client Configuration that is needed by the authenticator
    """

    token_endpoint: str
    authorization_endpoint: str
    redirect_uri: str
    client_id: str
    device_authorization_endpoint: typing.Optional[str] = None
    scopes: typing.List[str] = None
    header_key: str = "authorization"


class ClientConfigStore(object):
    """
    Client Config store retrieve client config. this can be done in multiple ways
    """

    @abstractmethod
    def get_client_config(self) -> ClientConfig:
        ...


class StaticClientConfigStore(ClientConfigStore):
    def __init__(self, cfg: ClientConfig):
        self._cfg = cfg

    def get_client_config(self) -> ClientConfig:
        return self._cfg


class Authenticator(object):
    """
    Base authenticator for all authentication flows
    """

    def __init__(self, endpoint: str, header_key: str, credentials: Credentials = None):
        self._endpoint = endpoint
        self._creds = credentials
        self._header_key = header_key if header_key else "authorization"

    def get_credentials(self) -> Credentials:
        return self._creds

    def _set_credentials(self, creds):
        self._creds = creds

    def _set_header_key(self, h: str):
        self._header_key = h

    def fetch_grpc_call_auth_metadata(self) -> typing.Optional[typing.Tuple[str, str]]:
        if self._creds:
            return self._header_key, f"Bearer {self._creds.access_token}"
        return None

    @abstractmethod
    def refresh_credentials(self):
        ...


class PKCEAuthenticator(Authenticator):
    """
    This Authenticator encapsulates the entire PKCE flow and automatically opens a browser window for login
    """

    def __init__(
            self,
            endpoint: str,
            cfg_store: ClientConfigStore,
            header_key: typing.Optional[str] = None,
            verify: typing.Optional[typing.Union[bool, str]] = None,
    ):
        """
        Initialize with default creds from KeyStore using the endpoint name
        """
        super().__init__(endpoint, header_key, KeyringStore.retrieve(endpoint))
        self._cfg_store = cfg_store
        self._auth_client = None
        self._verify = verify

    def _initialize_auth_client(self):
        if not self._auth_client:
            cfg = self._cfg_store.get_client_config()
            self._set_header_key(cfg.header_key)
            self._auth_client = AuthorizationClient(
                endpoint=self._endpoint,
                redirect_uri=cfg.redirect_uri,
                client_id=cfg.client_id,
                scopes=cfg.scopes,
                auth_endpoint=cfg.authorization_endpoint,
                token_endpoint=cfg.token_endpoint,
                verify=self._verify,
            )

    def refresh_credentials(self):
        """ """
        self._initialize_auth_client()
        if self._creds:
            """We have an access token so lets try to refresh it"""
            try:
                self._creds = self._auth_client.refresh_access_token(self._creds)
                if self._creds:
                    KeyringStore.store(self._creds)
                return
            except AccessTokenNotFoundError:
                logging.warning("Failed to refresh token. Kicking off a full authorization flow.")
                KeyringStore.delete(self._endpoint)

        self._creds = self._auth_client.get_creds_from_remote()
        KeyringStore.store(self._creds)


class CommandAuthenticator(Authenticator):
    """
    This Authenticator retreives access_token using the provided command
    """

    def __init__(self, command: typing.List[str], header_key: str = None):
        self._cmd = command
        if not self._cmd:
            raise AuthenticationError("Command cannot be empty for command authenticator")
        super().__init__(None, header_key)

    def refresh_credentials(self):
        """
        This function is used when the configuration value for AUTH_MODE is set to 'external_process'.
        It reads an id token generated by an external process started by running the 'command'.
        """
        logging.debug("Starting external process to generate id token. Command {}".format(self._cmd))
        try:
            output = subprocess.run(self._cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            logging.error("Failed to generate token from command {}".format(self._cmd))
            raise AuthenticationError("Problems refreshing token with command: " + str(e))
        self._creds = Credentials(output.stdout.strip())


class ClientCredentialsAuthenticator(Authenticator):
    """
    This Authenticator uses ClientId and ClientSecret to authenticate
    """

    _utf_8 = "utf-8"

    def __init__(
            self,
            endpoint: str,
            client_id: str,
            client_secret: str,
            cfg_store: ClientConfigStore,
            header_key: str = None,
    ):
        if not client_id or not client_secret:
            raise ValueError("Client ID and Client SECRET both are required.")
        cfg = cfg_store.get_client_config()
        self._token_endpoint = cfg.token_endpoint
        self._scopes = cfg.scopes
        self._client_id = client_id
        self._client_secret = client_secret
        super().__init__(endpoint, cfg.header_key or header_key)

    @staticmethod
    def get_token(token_endpoint: str, authorization_header: str, scopes: typing.List[str]) -> typing.Tuple[str, int]:
        """
        :rtype: (Text,Int) The first element is the access token retrieved from the IDP, the second is the expiration
                in seconds
        """
        headers = {
            "Authorization": authorization_header,
            "Cache-Control": "no-cache",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        body = {
            "grant_type": "client_credentials",
        }
        if scopes is not None:
            body["scope"] = ",".join(scopes)
        response = requests.post(token_endpoint, data=body, headers=headers)
        if response.status_code != 200:
            logging.error("Non-200 ({}) received from IDP: {}".format(response.status_code, response.text))
            raise AuthenticationError("Non-200 received from IDP")

        response = response.json()
        return response["access_token"], response["expires_in"]

    @staticmethod
    def get_basic_authorization_header(client_id: str, client_secret: str) -> str:
        """
        This function transforms the client id and the client secret into a header that conforms with http basic auth.
        It joins the id and the secret with a : then base64 encodes it, then adds the appropriate text

        :param client_id: str
        :param client_secret: str
        :rtype: str
        """
        concated = "{}:{}".format(client_id, client_secret)
        return "Basic {}".format(
            base64.b64encode(concated.encode(ClientCredentialsAuthenticator._utf_8)).decode(
                ClientCredentialsAuthenticator._utf_8
            )
        )

    def refresh_credentials(self):
        """
        This function is used by the _handle_rpc_error() decorator, depending on the AUTH_MODE config object. This handler
        is meant for SDK use-cases of auth (like pyflyte, or when users call SDK functions that require access to Admin,
        like when waiting for another workflow to complete from within a task). This function uses basic auth, which means
        the credentials for basic auth must be present from wherever this code is running.

        """
        token_endpoint = self._token_endpoint
        scopes = self._scopes

        # Note that unlike the Pkce flow, the client ID does not come from Admin.
        logging.debug(f"Basic authorization flow with client id {self._client_id} scope {scopes}")
        authorization_header = self.get_basic_authorization_header(self._client_id, self._client_secret)
        token, expires_in = self.get_token(token_endpoint, authorization_header, scopes)
        logging.info("Retrieved new token, expires in {}".format(expires_in))
        self._creds = Credentials(token)


class DeviceCodeAuthenticator(Authenticator):
    """
    This Authenticator implements the Device Code authorization flow useful for headless user authentication.

    Examples described
    - https://developer.okta.com/docs/guides/device-authorization-grant/main/
    - https://auth0.com/docs/get-started/authentication-and-authorization-flow/device-authorization-flow#device-flow
    """

    def __init__(self,
                 endpoint: str,
                 cfg_store: ClientConfigStore,
                 header_key: typing.Optional[str] = None,
                 audience: typing.Optional[str] = None):
        pass

    def _get_code(self):
        pass

    def _poll(self):
        pass

    def _get_token(self):
        pass
    
    def refresh_credentials(self):
        pass
