"""Uploads files to Steam Cloud under Tabletop Simulator's app id and shares them publicly.

This is exactly what TTS's own Cloud Manager does: ISteamRemoteStorage::FileWrite followed by FileShare, which
yields a UGC handle that Steam serves from its public content CDN. Requires the Steam client to be running
and logged in to an account that owns Tabletop Simulator.
"""
import ctypes
import hashlib
import os
import time
from pathlib import Path

from deckart_studio.hosting.steam_install import TABLETOP_SIMULATOR_APP_ID, find_steam_api_dll

FILE_SHARE_CALLBACK_ID = 1307
STEAM_FILENAME_MAX = 260
STEAM_ERROR_MESSAGE_MAX = 1024
INIT_RESULT_OK = 0
RESULT_OK = 1
POLL_INTERVAL_SECONDS = 0.1
SHARE_TIMEOUT_SECONDS = 180
PUBLIC_URL_TEMPLATE = "https://steamusercontent-a.akamaihd.net/ugc/{handle}/{sha1}/"

SteamAPICall = ctypes.c_uint64
UGCHandle = ctypes.c_uint64


class SteamCloudError(RuntimeError):
    pass


class FileShareResult(ctypes.Structure):
    _fields_ = [("result", ctypes.c_int32), ("file_handle", UGCHandle), ("filename", ctypes.c_char * STEAM_FILENAME_MAX)]


class SteamCloud:
    """A session against Steam Cloud for the TTS app id; use as a context manager."""

    def __init__(self, dll_path: Path | None = None):
        self.dll_path = dll_path or find_steam_api_dll()
        self._lib: ctypes.CDLL | None = None
        self._storage: int = 0
        self._utils: int = 0

    def __enter__(self) -> "SteamCloud":
        self.open()
        return self

    def __exit__(self, *_exc_info) -> None:
        self.close()

    def open(self) -> None:
        if self.dll_path is None or not Path(self.dll_path).exists():
            raise SteamCloudError("Tabletop Simulator's steam_api64.dll was not found. Is TTS installed through Steam?")
        os.environ["SteamAppId"] = str(TABLETOP_SIMULATOR_APP_ID)
        os.environ["SteamGameId"] = str(TABLETOP_SIMULATOR_APP_ID)
        self._lib = ctypes.CDLL(str(self.dll_path))
        self._declare_prototypes()
        self._init_steam()
        self._storage = self._lib.SteamAPI_SteamRemoteStorage_v016()
        self._utils = self._lib.SteamAPI_SteamUtils_v010()
        if not self._storage or not self._utils:
            raise SteamCloudError("Steam Cloud interfaces are unavailable in this steam_api64.dll.")

    def _init_steam(self) -> None:
        error_message = ctypes.create_string_buffer(STEAM_ERROR_MESSAGE_MAX)
        init_result = self._lib.SteamAPI_InitFlat(error_message)
        if init_result != INIT_RESULT_OK:
            detail = error_message.value.decode("utf-8", errors="replace").strip()
            raise SteamCloudError("Could not connect to Steam. Make sure Steam is running, you are logged in, and this "
                                  f"account owns Tabletop Simulator.\n{detail}")

    def close(self) -> None:
        if self._lib is not None and self._storage:
            self._lib.SteamAPI_Shutdown()
        self._storage = self._utils = 0

    def quota(self) -> tuple[int, int]:
        total, available = ctypes.c_uint64(), ctypes.c_uint64()
        self._lib.SteamAPI_ISteamRemoteStorage_GetQuota(self._storage, ctypes.byref(total), ctypes.byref(available))
        return total.value, available.value

    def upload(self, cloud_filename: str, data: bytes) -> str:
        """Write `data` to the cloud file, share it, and return its public URL."""
        name = cloud_filename.encode("utf-8")
        if not self._lib.SteamAPI_ISteamRemoteStorage_FileWrite(self._storage, name, data, len(data)):
            raise SteamCloudError(f"Steam refused to write {cloud_filename} ({len(data) / 1e6:.1f} MB). "
                                  "Cloud quota may be full - check Steam > Settings > Cloud.")
        share_call = self._lib.SteamAPI_ISteamRemoteStorage_FileShare(self._storage, name)
        result = self._await_share(share_call)
        return public_url(result.file_handle, hashlib.sha1(data).hexdigest())

    def _await_share(self, call: int) -> FileShareResult:
        failed = ctypes.c_bool(False)
        deadline = time.monotonic() + SHARE_TIMEOUT_SECONDS
        while not self._lib.SteamAPI_ISteamUtils_IsAPICallCompleted(self._utils, call, ctypes.byref(failed)):
            if time.monotonic() > deadline:
                raise SteamCloudError("Timed out waiting for Steam to share the file.")
            self._lib.SteamAPI_RunCallbacks()
            time.sleep(POLL_INTERVAL_SECONDS)
        return self._read_share_result(call)

    def _read_share_result(self, call: int) -> FileShareResult:
        result = FileShareResult()
        failed = ctypes.c_bool(False)
        fetched = self._lib.SteamAPI_ISteamUtils_GetAPICallResult(
            self._utils, call, ctypes.byref(result), ctypes.sizeof(result), FILE_SHARE_CALLBACK_ID, ctypes.byref(failed))
        if not fetched or failed.value or result.result != RESULT_OK:
            raise SteamCloudError(f"Steam FileShare failed (EResult {result.result}).")
        return result

    def _declare_prototypes(self) -> None:
        lib = self._lib
        lib.SteamAPI_InitFlat.restype = ctypes.c_int
        lib.SteamAPI_InitFlat.argtypes = [ctypes.c_char_p]
        lib.SteamAPI_Shutdown.restype = None
        lib.SteamAPI_RunCallbacks.restype = None
        lib.SteamAPI_SteamRemoteStorage_v016.restype = ctypes.c_void_p
        lib.SteamAPI_SteamUtils_v010.restype = ctypes.c_void_p
        lib.SteamAPI_ISteamRemoteStorage_FileWrite.restype = ctypes.c_bool
        lib.SteamAPI_ISteamRemoteStorage_FileWrite.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int32]
        lib.SteamAPI_ISteamRemoteStorage_FileShare.restype = SteamAPICall
        lib.SteamAPI_ISteamRemoteStorage_FileShare.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.SteamAPI_ISteamRemoteStorage_GetQuota.restype = ctypes.c_bool
        lib.SteamAPI_ISteamRemoteStorage_GetQuota.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64),
                                                             ctypes.POINTER(ctypes.c_uint64)]
        lib.SteamAPI_ISteamUtils_IsAPICallCompleted.restype = ctypes.c_bool
        lib.SteamAPI_ISteamUtils_IsAPICallCompleted.argtypes = [ctypes.c_void_p, SteamAPICall, ctypes.POINTER(ctypes.c_bool)]
        lib.SteamAPI_ISteamUtils_GetAPICallResult.restype = ctypes.c_bool
        lib.SteamAPI_ISteamUtils_GetAPICallResult.argtypes = [ctypes.c_void_p, SteamAPICall, ctypes.c_void_p, ctypes.c_int,
                                                             ctypes.c_int, ctypes.POINTER(ctypes.c_bool)]


def public_url(file_handle: int, sha1_hex: str) -> str:
    return PUBLIC_URL_TEMPLATE.format(handle=file_handle, sha1=sha1_hex.upper())


def cloud_filename_for(deck_name: str, source: Path, data: bytes) -> str:
    digest = hashlib.sha1(data).hexdigest()[:10]
    safe_deck = safe_cloud_component(deck_name)[:40]
    safe_stem = safe_cloud_component(source.stem)[:60]
    return f"DeckArtStudio_{safe_deck}_{safe_stem}_{digest}{source.suffix.lower()}"


def safe_cloud_component(text: str) -> str:
    return "".join(character if character.isalnum() or character in "-_" else "_" for character in text) or "file"
