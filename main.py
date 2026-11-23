#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KrakazeSkamBase (@KrakazeBaseApp) - Telegram Anti-Scam Bot (24/7)
- Открытый доступ для всех пользователей + кнопка «Админ-панель» для администраторов.
- Минималистичная Liquid Glass карточка главного меню (только название и «Антискам-бот»).
- Карточки профилей (Непроверенный / Скамер / Гарант) с настоящим эффектом жидкого стекла
  (оптическое преломление краёв, матовое размытие, спекулярные блики, каустика и кант)
  поверх спокойного тонового фона без визуального шума.
- Расширенное HTML-форматирование: цитаты (blockquote / expandable), жирный, подчёркивание,
  курсив, моноширинный код, ссылки, кастомные эмодзи и разноцветные кнопки Bot API.
- Совместная отправка фото/видео доказательств альбомом (send_media_group) + сохранение пруфов.
- Круговая ротация нерассмотренных жалоб между администраторами каждый час (3600 сек).
"""

import asyncio
import atexit
import base64
import gzip
import hashlib
import html
import inspect
import io
import json
import logging
import math
import os
import random
import re
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
import traceback
import unicodedata
import urllib.parse
import urllib.request
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputMediaPhoto,
    InputMediaVideo,
    InputTextMessageContent,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)

try:
    from telegram import InlineQueryResultsButton
except ImportError:
    InlineQueryResultsButton = None

try:
    from telegram import LinkPreviewOptions
except ImportError:
    LinkPreviewOptions = None

try:
    from telegram.warnings import PTBUserWarning
    warnings.filterwarnings("ignore", category=PTBUserWarning)
except Exception:
    warnings.filterwarnings("ignore", message=".*per_message.*")

try:
    from telegram import KeyboardButtonRequestUsers
except ImportError:
    KeyboardButtonRequestUsers = None

try:
    from telegram import KeyboardButtonRequestUser
except ImportError:
    KeyboardButtonRequestUser = None

from telegram.constants import ChatType, ParseMode
from telegram.error import BadRequest, Forbidden, NetworkError, RetryAfter, TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    Defaults,
    InlineQueryHandler,
    MessageHandler,
    filters,
)

# Опциональный Firebase Admin SDK (при отсутствии используется встроенный REST API)
try:
    import firebase_admin
    from firebase_admin import (
        credentials as fb_credentials,
        firestore as fb_firestore,
    )
    FIREBASE_ADMIN_AVAILABLE = True
except ImportError:
    firebase_admin = None
    fb_credentials = None
    fb_firestore = None
    FIREBASE_ADMIN_AVAILABLE = False

# =====================================================================
# КОНФИГУРАЦИЯ БОТА
# =====================================================================
BOT_NAME = "KrakazeSkamBase"
BOT_USERNAME = "@KrakazeBaseApp"
BOT_URL = "https://t.me/KrakazeBaseApp"

BOT_TOKEN = os.environ.get("BOT_TOKEN", "9065482185:AAGw1Ta4JVgqj9gunQSAjVrfwfxl4gMyZik")
ADMIN_IDS: List[int] = [7459502130, 684535319]  # Главные администраторы (полные права)
ADMIN_IDS_SET = set(ADMIN_IDS)

# Опциональные Telegram API ID / Hash для глобального MTProto-определителя ID (my.telegram.org)
TG_API_ID = int(os.environ.get("TG_API_ID") or os.environ.get("API_ID") or "0")
TG_API_HASH = (os.environ.get("TG_API_HASH") or os.environ.get("API_HASH") or "").strip()

REPORT_ROTATION_SECONDS = 3600  # 1 час на рассмотрение заявки одним модератором/админом
MAX_REPORT_MEDIA = 20

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "base.db"
LEGACY_DB_PATH = BASE_DIR / "scam_base.db"
FONTS_DIR = BASE_DIR / "fonts"
AVATARS_CACHE_DIR = BASE_DIR / "avatars_cache"

FONTS_DIR.mkdir(parents=True, exist_ok=True)
AVATARS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

START_TIME = time.time()
_FALLBACK_ROTATION_TASK: Optional[asyncio.Task] = None

logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("krakaze_scam_base")

# =====================================================================
# FIREBASE CLOUD FIRESTORE (НОВАЯ КОЛЛЕКЦИЯ telegram_scam_base -> base.db)
# =====================================================================
FIREBASE_SERVICE_ACCOUNT_CONFIG = {
    "type": "service_account",
    "project_id": "proar-5a642",
    "private_key_id": "039601a8db0c82988fe7ea83c3a3463301d7cd8b",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDZpDGlnJ67Qoxu\nGlxikHVtThmN7PdrOXKvVd7Nko2XWs8UZboV/6KmHREN3pEjzwdQb3tXGnWwwR+s\nnUkH5ILGoUpQ88XSxrbgTtKOU8TJbaIye8MmSDTmXHmwxRiMum/BfBdaoPR02P8P\nfLoP4ihwnKe8l7PRFRaybDungKuG7wIzCEUiZy828+DZk24z1ymqyrOwo0JSMpUI\nFWtCQb7cNTt1u9LOfCTCXKP46GTg2ghjYIUqQpVgX3zR4koKLuYava4vrNVAJT9B\nXiL+/YNGnvct5ZKT1OiHh8V4x7o2jN0R2D5sQ03z/Us6CB2LC/9NNQIxsnXp/gzB\nLvqbv94ZAgMBAAECggEABRkespmZxvAsTZ30y7hE5T5pmdSoXQzM8299rG9s5/6Q\nED3BH1J20xD7knQZY+8tutl0WFoofJn22HpyDgBxJx77GIIFVcZ4MoaWJxBY8Tuj\nYNmw/Ly/RHrREkN5AOmTGZittrPuK1iJQlRydVHKZGI/CaC8wmk4jWMR/f6lG0rY\nlLDLNCE9a6c6lLfEL72K7JRmRfbW96DIEnx6ObcqkPzaYb+pz24ewsUkY5b2QVZe\nifrQN2gAqNGq34qVp1m4/ywVC5E40sie0Un2nmINPqEA0VzVllEwgcCd5bx2X8Ya\nI2OW3TnvnoHtxNdXXY04advOMohHpNTdPd2Z5awYQQKBgQD1euUTbnEt8qcXRZYU\nmKEL5P4FvPQ7Ly3vQ8vGd7oK7lLE0zY+nEE1TW5mAaNM1W6QzZSAQsfUq8k1QZLI\n4m70f//UcnvADi/Ke12ze1xxCtHYADYb04bQ4CjfjtLk5ZstjO31mVqkNQXiSUo2\nTXYTpsi93zxj9SHaa6HT5F0zkQKBgQDi9+MtUw6ChXoiVF6V3C5AU5mtJA1eRdQy\n8AZ9GTrPAGh5ewVG+Nl9VG3ePIbZkmquh2zEo2f0LgPczegVIqDz0VBIW4LIw4wT\nmNG7MSOtJg2/wpoZexw7y1BknkWi8aV26BkEgxDEIXvvjUC3tHD9V0m2BZ4lVlsr\ng6+ZLWUuCQKBgC7JhJ3GgAXc6OHznl5AlPlaZNwdHoOlQ2EGD/G84hWxRM9E3mLi\njz8kifUhPMmpKFCrDjHACKxNLaVb4Skuly08tDr+sv1w9sTl7H8H9R+Ki2Ja7/Uv\nxNNM1h198E42QPRWlwgneXIwtPVjOKTO8MFgGYSu5qi6kQA7YXWsYeMxAoGBAItB\ncH9UoGhwoNkDTu0/pJkPMhDLN/CJg4KlRjXnDvAG3hL66ef7suV0sdxS4qIHdbET\noiab46IrwW7uXuDo2DwARvO+QeYQJJe5gaUKp0sLOBBZw9aydEYznmW9vhgVj2H/\nUao1CEpuCO6XigesjE7ECZPGqptZ+qIeL9UZxySRAoGBAIkU8wfatRMbuPmzgtst\nhEZt62FEe+0MP1QfPY6ByddLnzqlO6JpWRNUXkx6zFjf3Vy7J/J+fClAo10E4uWh\nFe7HkfG/CCamiAB4ki1WiSrrQkB/FtJAaBI3y4Ka1jN6IzniVJ0pH1Nb9N8+x8eE\nMSgIEVIFGwIPv3vQofyxnnTr\n-----END PRIVATE KEY-----\n",
    "client_email": "firebase-adminsdk-fbsvc@proar-5a642.iam.gserviceaccount.com",
    "client_id": "103737744652283306114",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40proar-5a642.iam.gserviceaccount.com",
    "universe_domain": "googleapis.com",
}

_SHA256_DIGEST_INFO_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")


def _read_der_element(data: bytes, offset: int) -> Tuple[int, bytes, int]:
    """Читает один ASN.1 DER-элемент и возвращает (tag, content_bytes, next_offset)."""
    if offset >= len(data):
        raise ValueError("Неожиданный конец DER-структуры")
    tag = data[offset]
    offset += 1
    first_len = data[offset]
    offset += 1
    if first_len & 0x80:
        num_octets = first_len & 0x7F
        if num_octets == 0:
            raise ValueError("Неопределённая длина DER не поддерживается")
        length = int.from_bytes(data[offset : offset + num_octets], "big")
        offset += num_octets
    else:
        length = first_len
    end = offset + length
    if end > len(data):
        raise ValueError("Длина DER-элемента выходит за пределы буфера")
    return tag, data[offset:end], end


def _parse_rsa_private_key_pem(pem_text: str) -> Tuple[int, int]:
    """
    Извлекает (n, d) из PEM-ключа PKCS#8 (BEGIN PRIVATE KEY) или PKCS#1 (BEGIN RSA PRIVATE KEY)
    без использования внешних утилит вроде openssl.
    """
    normalized = pem_text.replace("\\n", "\n").strip()
    b64_lines = [
        line.strip()
        for line in normalized.splitlines()
        if line.strip() and not line.strip().startswith("-----")
    ]
    der_bytes = base64.b64decode("".join(b64_lines))

    tag, seq_body, _ = _read_der_element(der_bytes, 0)
    if tag != 0x30:
        raise ValueError("Ожидалась корневая DER SEQUENCE")

    # Читаем первые поля корневой последовательности
    fields: List[Tuple[int, bytes]] = []
    pos = 0
    while pos < len(seq_body):
        f_tag, f_val, pos = _read_der_element(seq_body, pos)
        fields.append((f_tag, f_val))

    # PKCS#8: [INTEGER version, SEQUENCE algorithm, OCTET STRING privateKey, ...]
    if len(fields) >= 3 and fields[0][0] == 0x02 and fields[1][0] == 0x30 and fields[2][0] == 0x04:
        inner_tag, inner_body, _ = _read_der_element(fields[2][1], 0)
        if inner_tag != 0x30:
            raise ValueError("Ожидалась внутренняя RSAPrivateKey SEQUENCE")
        rsa_fields: List[Tuple[int, bytes]] = []
        rpos = 0
        while rpos < len(inner_body):
            rt, rv, rpos = _read_der_element(inner_body, rpos)
            rsa_fields.append((rt, rv))
        fields = rsa_fields

    # RSAPrivateKey: [version, modulus(n), publicExponent(e), privateExponent(d), ...]
    if len(fields) < 4 or fields[1][0] != 0x02 or fields[3][0] != 0x02:
        raise ValueError("Некорректная структура RSAPrivateKey")

    n = int.from_bytes(fields[1][1], "big")
    d = int.from_bytes(fields[3][1], "big")
    return n, d


def _sign_rs256_pure_python(message_bytes: bytes, pem_private_key: str) -> bytes:
    """Подписывает данные алгоритмом RSASSA-PKCS1-v1_5 + SHA-256 на чистом Python."""
    n, d = _parse_rsa_private_key_pem(pem_private_key)
    k_len = (n.bit_length() + 7) // 8
    digest = hashlib.sha256(message_bytes).digest()
    digest_info = _SHA256_DIGEST_INFO_PREFIX + digest
    ps_len = k_len - len(digest_info) - 3
    if ps_len < 8:
        raise ValueError("Слишком короткий RSA-ключ для SHA-256")
    em = b"\x00\x01" + (b"\xff" * ps_len) + b"\x00" + digest_info
    sig_int = pow(int.from_bytes(em, "big"), d, n)
    return sig_int.to_bytes(k_len, "big")


def migrate_legacy_db_if_needed() -> None:
    """Переносит локальную scam_base.db в base.db, если base.db ещё не создана."""
    try:
        if not DB_PATH.exists() and LEGACY_DB_PATH.exists() and LEGACY_DB_PATH.stat().st_size >= 100:
            shutil.copy2(LEGACY_DB_PATH, DB_PATH)
            logger.info("Локальная база %s перенесена в %s", LEGACY_DB_PATH.name, DB_PATH.name)
    except Exception as e:
        logger.warning("Не удалось перенести legacy-базу %s -> %s: %s", LEGACY_DB_PATH.name, DB_PATH.name, e)


class FirebaseCloudManager:
    """
    Облачное хранение SQLite-базы антискам-бота (base.db) в отдельной коллекции
    Cloud Firestore `telegram_scam_base` (Telegram Scam Base), без пересечения с другими ботами.
    """

    def __init__(self) -> None:
        self.project_id: str = "proar-5a642"
        self.collection_name: str = "telegram_scam_base"
        self.doc_name: str = "sqlite_database"
        self.display_name: str = "Telegram Scam Base"
        self.app = None
        self.firestore_client = None
        self.cached_token: Optional[str] = None
        self.token_expiry: float = 0.0
        self.initialized: bool = False
        self.active_key_id: str = "embedded"
        self.loaded_cred_dict: Optional[dict] = None
        self.last_sync_ts: float = 0.0
        self.last_sync_size: int = 0
        self.last_sync_status: str = "Ожидает первой синхронизации"
        self._lock = threading.Lock()
        self._sync_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._dirty: bool = False
        self._startup_download_error: bool = False
        self._cloud_doc_missing: bool = False

    @staticmethod
    def format_error(e: Exception) -> str:
        err_msg = str(e)
        if "Invalid JWT Signature" in err_msg or "invalid_grant" in err_msg:
            return "Ключ сервисного аккаунта отозван в консоли Firebase (Invalid JWT Signature)."
        if "permission" in err_msg.lower() or "403" in err_msg:
            return "Ошибка доступа: проверьте права сервисного аккаунта в Firebase Console."
        safe_msg = re.sub(r"<[^>]+>", "", err_msg)
        return f"Ошибка: {safe_msg[:200]}"

    def get_access_token(self) -> Optional[str]:
        now = time.time()
        if self.cached_token and self.token_expiry > now + 120:
            return self.cached_token

        key_dict = self.loaded_cred_dict or dict(FIREBASE_SERVICE_ACCOUNT_CONFIG)
        try:
            from google.oauth2 import service_account
            from google.auth.transport.requests import Request
            scopes = [
                "https://www.googleapis.com/auth/datastore",
                "https://www.googleapis.com/auth/cloud-platform",
            ]
            creds = service_account.Credentials.from_service_account_info(key_dict, scopes=scopes)
            creds.refresh(Request())
            self.cached_token = creds.token
            self.token_expiry = now + 3500
            return self.cached_token
        except Exception:
            pass

        try:
            header = {"alg": "RS256", "typ": "JWT"}
            iat = int(now)
            payload = {
                "iss": key_dict["client_email"],
                "scope": "https://www.googleapis.com/auth/datastore https://www.googleapis.com/auth/cloud-platform",
                "aud": "https://oauth2.googleapis.com/token",
                "exp": iat + 3600,
                "iat": iat,
            }

            def b64url(b: bytes) -> str:
                return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")

            eh = b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
            ep = b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
            si = f"{eh}.{ep}".encode("utf-8")
            pem_key = key_dict["private_key"].replace("\\n", "\n")

            sig: Optional[bytes] = None
            # 1. cryptography (если установлена)
            try:
                from cryptography.hazmat.primitives import hashes, serialization
                from cryptography.hazmat.primitives.asymmetric import padding as asym_padding

                priv = serialization.load_pem_private_key(pem_key.encode("utf-8"), password=None)
                sig = priv.sign(si, asym_padding.PKCS1v15(), hashes.SHA256())
            except Exception:
                sig = None

            # 2. Чистый Python RS256 (работает везде, включая Android / Pydroid3 без openssl)
            if sig is None:
                try:
                    sig = _sign_rs256_pure_python(si, pem_key)
                except Exception:
                    sig = None

            # 3. Запасной вариант через openssl CLI, если присутствует в системе
            if sig is None:
                kf_path = None
                df_path = None
                try:
                    with tempfile.NamedTemporaryFile("w", delete=False) as kf, tempfile.NamedTemporaryFile("wb", delete=False) as df:
                        kf.write(pem_key)
                        kf.flush()
                        df.write(si)
                        df.flush()
                        kf_path = kf.name
                        df_path = df.name
                    sig = subprocess.check_output(["openssl", "dgst", "-sha256", "-sign", kf_path, df_path])
                finally:
                    for p in (kf_path, df_path):
                        if p and os.path.exists(p):
                            try:
                                os.unlink(p)
                            except Exception:
                                pass

            assertion = f"{eh}.{ep}.{b64url(sig)}"
            token_resp = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
                timeout=15,
            )
            if token_resp.status_code != 200:
                raise RuntimeError(f"OAuth2 HTTP {token_resp.status_code}: {token_resp.text[:250]}")
            res = token_resp.json()
            self.cached_token = res["access_token"]
            self.token_expiry = now + int(res.get("expires_in", 3600)) - 60
            return self.cached_token
        except Exception as ex:
            logger.warning("[Firebase Cloud] Не удалось получить OAuth2 токен: %s", ex)
            return None

    def init_app(self, force_reload: bool = False) -> bool:
        if self.initialized and not force_reload:
            return True

        candidate_files = [
            BASE_DIR / "firebase-service-account.json",
            BASE_DIR / "firebase_credentials.json",
        ]
        try:
            candidate_files += sorted(list(BASE_DIR.glob("*firebase*adminsdk*.json")), key=lambda p: p.stat().st_mtime, reverse=True)
            candidate_files += sorted(list(BASE_DIR.glob("*proar-5a642*.json")), key=lambda p: p.stat().st_mtime, reverse=True)
        except Exception:
            pass

        cred_dict = None
        loaded_source = "встроенного ключа"

        for candidate in candidate_files:
            if candidate.exists() and candidate.is_file() and candidate.stat().st_size > 50:
                try:
                    with open(candidate, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if "private_key" in data and "client_email" in data:
                            data["private_key"] = data["private_key"].replace("\\n", "\n")
                            cred_dict = data
                            loaded_source = candidate.name
                            self.active_key_id = data.get("private_key_id", "external")
                            break
                except Exception as ex:
                    logger.warning("[Firebase] Ошибка чтения %s: %s", candidate, ex)

        if not cred_dict:
            cred_dict = dict(FIREBASE_SERVICE_ACCOUNT_CONFIG)
            cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
            self.active_key_id = cred_dict.get("private_key_id", "embedded")

        self.loaded_cred_dict = cred_dict
        self.project_id = cred_dict.get("project_id", "proar-5a642")

        if FIREBASE_ADMIN_AVAILABLE and fb_firestore and fb_credentials:
            try:
                if force_reload and self.app:
                    try:
                        firebase_admin.delete_app(self.app)
                    except Exception:
                        pass
                    self.app = None

                cred = fb_credentials.Certificate(cred_dict)
                try:
                    self.app = firebase_admin.get_app()
                except ValueError:
                    self.app = firebase_admin.initialize_app(cred, {"projectId": self.project_id})
                self.firestore_client = fb_firestore.client(app=self.app)
                logger.info("[Firebase] Cloud Firestore SDK инициализирован (%s, коллекция=%s)", loaded_source, self.collection_name)
            except Exception as e:
                logger.warning("[Firebase] Не удалось запустить Firestore SDK, переключение на REST API: %s", e)
                self.firestore_client = None

        self.initialized = True
        return True

    @staticmethod
    def is_valid_sqlite(path: Path) -> bool:
        if not path.exists() or path.stat().st_size < 100:
            return False
        try:
            with open(path, "rb") as f:
                return f.read(16) == b"SQLite format 3\x00"
        except Exception:
            return False

    @staticmethod
    def _count_local_records(path: Path) -> int:
        if not path.exists():
            return 0
        total = 0
        conn = None
        try:
            conn = sqlite3.connect(path)
            for table in ("scammers", "guarantors", "scam_reports", "moderators", "user_agreements"):
                try:
                    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                    if row:
                        total += int(row[0] or 0)
                except Exception:
                    pass
            return total
        except Exception:
            return 0
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def _cloud_doc_exists(self) -> Optional[bool]:
        if self.firestore_client:
            try:
                snap = self.firestore_client.collection(self.collection_name).document(self.doc_name).get()
                return bool(snap.exists)
            except Exception:
                pass
        token = self.get_access_token()
        if not token:
            return None
        doc_url = (
            f"https://firestore.googleapis.com/v1/projects/{self.project_id}"
            f"/databases/(default)/documents/{self.collection_name}/{self.doc_name}"
        )
        req = urllib.request.Request(doc_url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=12):
                return True
        except urllib.error.HTTPError as he:
            if he.code == 404:
                return False
            return None
        except Exception:
            return None

    def download_db_on_startup(self) -> bool:
        if not self.init_app():
            self._startup_download_error = True
            return False

        try:
            b64_data = None
            doc_found = False

            if self.firestore_client:
                try:
                    doc_ref = self.firestore_client.collection(self.collection_name).document(self.doc_name)
                    doc = doc_ref.get()
                    if doc.exists:
                        doc_found = True
                        data = doc.to_dict() or {}
                        b64_data = data.get("data_gzip_b64")
                    else:
                        self._cloud_doc_missing = True
                except Exception as ex_sdk:
                    logger.warning("[Firebase] SDK get doc: %s, пробую REST...", ex_sdk)

            if not b64_data and not doc_found:
                token = self.get_access_token()
                if token:
                    doc_url = (
                        f"https://firestore.googleapis.com/v1/projects/{self.project_id}"
                        f"/databases/(default)/documents/{self.collection_name}/{self.doc_name}"
                    )
                    req = urllib.request.Request(doc_url, headers={"Authorization": f"Bearer {token}"})
                    try:
                        with urllib.request.urlopen(req, timeout=15) as r:
                            doc_json = json.loads(r.read().decode("utf-8"))
                            doc_found = True
                            fields = doc_json.get("fields", {})
                            b64_data = fields.get("data_gzip_b64", {}).get("stringValue")
                    except urllib.error.HTTPError as he:
                        if he.code == 404:
                            logger.info(
                                "[Firebase] Документ %s/%s в Firestore пока не создан - будет создана новая ячейка.",
                                self.collection_name,
                                self.doc_name,
                            )
                            self.last_sync_status = "Новая ячейка готова к выгрузке base.db"
                            self._cloud_doc_missing = True
                            self._startup_download_error = False
                            return False
                        raise

            if not doc_found and self._cloud_doc_missing:
                self.last_sync_status = "Новая ячейка готова к выгрузке base.db"
                self._startup_download_error = False
                return False

            if not b64_data:
                if doc_found:
                    logger.warning("[Firebase] Документ %s существует, но data_gzip_b64 пусто. Облако защищено.", self.collection_name)
                    self._startup_download_error = True
                else:
                    self.last_sync_status = "Новая ячейка готова к выгрузке base.db"
                    self._cloud_doc_missing = True
                return False

            raw_bytes = gzip.decompress(base64.b64decode(b64_data))
            if not raw_bytes.startswith(b"SQLite format 3\x00"):
                logger.error("[Firebase] Данные из %s не являются валидной SQLite базой!", self.collection_name)
                self._startup_download_error = True
                return False

            tmp_path = BASE_DIR / "base.db.tmp_download"
            with open(tmp_path, "wb") as f:
                f.write(raw_bytes)

            if DB_PATH.exists():
                try:
                    shutil.copy2(DB_PATH, BASE_DIR / "base.db.backup_local")
                except Exception:
                    pass

            shutil.move(tmp_path, DB_PATH)
            self.last_sync_ts = time.time()
            self.last_sync_size = len(raw_bytes)
            self._startup_download_error = False
            self._cloud_doc_missing = False
            self._dirty = False
            self.last_sync_status = f"Восстановлена из Firestore ({len(raw_bytes):,} байт)"
            logger.info("[Firebase] База base.db (%s байт) загружена из %s!", f"{len(raw_bytes):,}", self.collection_name)
            return True
        except Exception as e:
            logger.error("[Firebase] Ошибка скачивания base.db из Firestore: %s", e)
            self.last_sync_status = self.format_error(e)
            self._startup_download_error = True
            return False

    def upload_db_to_cloud(self, force: bool = False) -> bool:
        if not self.init_app():
            return False

        with self._lock:
            try:
                if self._startup_download_error and not force:
                    logger.warning("[Firebase] Anti-Wipe: ошибка чтения Firestore при старте, автовыгрузка заблокирована.")
                    return False

                if not DB_PATH.exists() or DB_PATH.stat().st_size < 100:
                    return False

                if not self.is_valid_sqlite(DB_PATH):
                    return False

                if not force and not self._dirty and not self._cloud_doc_missing:
                    return True

                if not force and self._count_local_records(DB_PATH) == 0 and not self._cloud_doc_missing:
                    exists = self._cloud_doc_exists()
                    if exists:
                        logger.warning("[Firebase] Anti-Wipe: локальная base.db пуста (0 записей), а в %s уже есть данные. Пропуск!", self.collection_name)
                        return False

                if not force and self.last_sync_ts > 0 and (time.time() - self.last_sync_ts < 12):
                    return True

                snapshot_path = BASE_DIR / "base.db.upload_snapshot"
                try:
                    src_conn = sqlite3.connect(DB_PATH)
                    dst_conn = sqlite3.connect(snapshot_path)
                    src_conn.backup(dst_conn)
                    dst_conn.close()
                    src_conn.close()
                    target_file = snapshot_path
                except Exception:
                    target_file = DB_PATH

                with open(target_file, "rb") as f:
                    raw_db = f.read()

                if snapshot_path.exists():
                    try:
                        snapshot_path.unlink()
                    except Exception:
                        pass

                if not raw_db.startswith(b"SQLite format 3\x00"):
                    return False

                current_size = len(raw_db)
                compressed = gzip.compress(raw_db, compresslevel=9)
                b64_data = base64.b64encode(compressed).decode("ascii")
                sha256_hash = hashlib.sha256(raw_db).hexdigest()
                now_utc = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
                now_ts = time.time()

                saved = False
                if self.firestore_client:
                    try:
                        doc_ref = self.firestore_client.collection(self.collection_name).document(self.doc_name)
                        doc_ref.set({
                            "project_tag": self.display_name,
                            "bot_username": BOT_USERNAME,
                            "database_file": "base.db",
                            "file_size": current_size,
                            "compressed_size": len(compressed),
                            "sha256": sha256_hash,
                            "updated_at": now_utc,
                            "updated_ts": now_ts,
                            "data_gzip_b64": b64_data,
                        })
                        saved = True
                    except Exception as ex_sdk:
                        logger.warning("[Firebase] Ошибка записи через SDK: %s, пробую REST...", ex_sdk)

                if not saved:
                    token = self.get_access_token()
                    if not token:
                        raise RuntimeError("Не удалось получить OAuth2 токен для Firestore")

                    doc_url = (
                        f"https://firestore.googleapis.com/v1/projects/{self.project_id}"
                        f"/databases/(default)/documents/{self.collection_name}/{self.doc_name}"
                    )
                    doc_body = json.dumps({
                        "fields": {
                            "project_tag": {"stringValue": self.display_name},
                            "bot_username": {"stringValue": BOT_USERNAME},
                            "database_file": {"stringValue": "base.db"},
                            "file_size": {"integerValue": str(current_size)},
                            "compressed_size": {"integerValue": str(len(compressed))},
                            "sha256": {"stringValue": sha256_hash},
                            "updated_at": {"stringValue": now_utc},
                            "updated_ts": {"doubleValue": now_ts},
                            "data_gzip_b64": {"stringValue": b64_data},
                        }
                    }).encode("utf-8")
                    req = urllib.request.Request(
                        doc_url,
                        data=doc_body,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json",
                        },
                        method="PATCH",
                    )
                    with urllib.request.urlopen(req, timeout=20) as resp:
                        if resp.status in (200, 201):
                            saved = True

                if saved:
                    self.last_sync_ts = time.time()
                    self.last_sync_size = current_size
                    self._cloud_doc_missing = False
                    self._startup_download_error = False
                    self._dirty = False
                    self.last_sync_status = (
                        f"Синхронизировано в {datetime.now().strftime('%H:%M:%S')} ({current_size:,} байт)"
                    )
                    logger.info(
                        "[Firebase] База base.db сохранена в %s/%s (%s -> %s байт)",
                        self.collection_name,
                        self.doc_name,
                        f"{current_size:,}",
                        f"{len(compressed):,}",
                    )
                    return True
                raise RuntimeError("Firestore не подтвердил сохранение документа")
            except Exception as e:
                logger.error("[Firebase] Ошибка выгрузки в Firestore: %s", e)
                self.last_sync_status = self.format_error(e)
                return False

    def schedule_sync(self) -> None:
        self._dirty = True

    def start_periodic_sync(self, interval_seconds: int = 60) -> None:
        if self._sync_thread and self._sync_thread.is_alive():
            return

        def _worker() -> None:
            while not self._stop_event.is_set():
                self._stop_event.wait(interval_seconds)
                if self._stop_event.is_set():
                    break
                try:
                    if self._dirty or self._cloud_doc_missing:
                        self.upload_db_to_cloud(force=False)
                except Exception as e:
                    logger.error("[Firebase Worker] Ошибка синхронизации: %s", e)

        self._sync_thread = threading.Thread(target=_worker, daemon=True, name="FirebaseSyncWorker")
        self._sync_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self.initialized and (self._dirty or self._cloud_doc_missing):
            self.upload_db_to_cloud(force=False)


firebase_manager = FirebaseCloudManager()


def _on_firebase_shutdown() -> None:
    try:
        firebase_manager.stop()
    except Exception:
        pass


atexit.register(_on_firebase_shutdown)

# FSM состояния
(
    # Админское добавление скамера / гаранта
    WAIT_SCAM_TARGET,
    WAIT_SCAM_REASON,
    WAIT_SCAM_DAMAGE,
    WAIT_SCAM_PROOF,
    WAIT_GUAR_TARGET,
    WAIT_GUAR_NOTE,
    # Пользовательская жалоба на скамера
    REP_WAIT_TARGET,
    REP_WAIT_DESC,
    REP_WAIT_MEDIA,
    REP_PREVIEW,
    REP_EDIT_TARGET,
    REP_EDIT_DESC,
    REP_EDIT_MEDIA,
    # Отклонение жалобы с причиной (админ/модератор)
    ADM_REJECT_REASON,
    # Управление модераторами, каналом пруфов, парсером и Firebase (только ADMIN_IDS)
    WAIT_MOD_TARGET,
    WAIT_CHANNEL_SET,
    WAIT_FB_JSON,
    WAIT_SCRAPE_CHANNEL,
) = range(18)

INITIAL_SEED_CHANNEL = "loneasproofs"


# =====================================================================
# КАСТОМНЫЕ ПРЕМИУМ-ЭМОДЗИ
# =====================================================================
EMOJI_META: Dict[str, Tuple[str, str]] = {
    "crown": ("5217822164362739968", "👑"),
    "siren": ("5395695537687123235", "🚨"),
    "no_entry": ("5260293700088511294", "⛔️"),
    "lock": ("5296369303661067030", "🔒"),
    "shield": ("5251203410396458957", "🛡"),
    "chart": ("5231200819986047254", "📊"),
    "refresh": ("5375338737028841420", "🔄"),
    "gear": ("5341715473882955310", "⚙️"),
    "check": ("5206607081334906820", "✔️"),
    "cross": ("5210952531676504517", "❌"),
    "eyes": ("5210956306952758910", "👀"),
    "warn": ("5447644880824181073", "⚠️"),
    "fire": ("5424972470023104089", "🔥"),
    "search": ("5231012545799666522", "🔍"),
    "trash": ("5445267414562389170", "🗑"),
    "plus": ("5397916757333654639", "➕"),
    "clock": ("5386367538735104399", "⌛"),
}

EMOJI_IDS: Dict[str, str] = {k: v[0] for k, v in EMOJI_META.items()}
EMOJI: Dict[str, str] = {
    k: f'<tg-emoji emoji-id="{eid}">{fallback}</tg-emoji>'
    for k, (eid, fallback) in EMOJI_META.items()
}


# =====================================================================
# СОВМЕСТИМЫЙ КОНСТРУКТОР РАЗНОЦВЕТНЫХ КНОПОК (TELEGRAM BOT API)
# =====================================================================
_IKB_PARAMS = inspect.signature(InlineKeyboardButton.__init__).parameters
_SUPPORTS_NATIVE_STYLE = "style" in _IKB_PARAMS
_SUPPORTS_NATIVE_ICON = "icon_custom_emoji_id" in _IKB_PARAMS


def make_btn(
    text: str,
    callback_data: Optional[str] = None,
    url: Optional[str] = None,
    style: Optional[str] = None,
    emoji_key: Optional[str] = None,
    with_icon: bool = True,
) -> InlineKeyboardButton:
    kwargs: dict = {"text": text}
    if callback_data is not None:
        # Ограничение Telegram API - максимум 64 байта
        kwargs["callback_data"] = callback_data[:64]
    elif url is not None:
        kwargs["url"] = url

    api_kwargs: dict = {}

    if style in ("primary", "success", "danger"):
        if _SUPPORTS_NATIVE_STYLE:
            kwargs["style"] = style
        else:
            api_kwargs["style"] = style

    icon_id = EMOJI_IDS.get(emoji_key) if (with_icon and emoji_key) else None
    if icon_id:
        if _SUPPORTS_NATIVE_ICON:
            kwargs["icon_custom_emoji_id"] = icon_id
        else:
            api_kwargs["icon_custom_emoji_id"] = icon_id

    if api_kwargs:
        kwargs["api_kwargs"] = api_kwargs

    return InlineKeyboardButton(**kwargs)


def build_select_user_reply_kb(with_style_and_icons: bool = True) -> ReplyKeyboardMarkup:
    """Клавиатура под строкой ввода с нативной кнопкой выбора пользователя Telegram."""
    _kb_params = inspect.signature(KeyboardButton.__init__).parameters
    btn_kwargs: Dict[str, Any] = {"text": "Выбрать пользователя"}
    cancel_kwargs: Dict[str, Any] = {"text": "Отмена"}

    if with_style_and_icons:
        if "style" in _kb_params:
            btn_kwargs["style"] = "primary"
            cancel_kwargs["style"] = "danger"
        if "icon_custom_emoji_id" in _kb_params:
            if EMOJI_IDS.get("search"):
                btn_kwargs["icon_custom_emoji_id"] = EMOJI_IDS["search"]
            if EMOJI_IDS.get("cross"):
                cancel_kwargs["icon_custom_emoji_id"] = EMOJI_IDS["cross"]

    if KeyboardButtonRequestUsers is not None and "request_users" in _kb_params:
        _req_params = inspect.signature(KeyboardButtonRequestUsers.__init__).parameters
        req_kwargs: Dict[str, Any] = {
            "request_id": 101,
            "user_is_bot": False,
            "max_quantity": 1,
        }
        if "request_name" in _req_params:
            req_kwargs["request_name"] = True
        if "request_username" in _req_params:
            req_kwargs["request_username"] = True
        if "request_photo" in _req_params:
            req_kwargs["request_photo"] = True
        btn_kwargs["request_users"] = KeyboardButtonRequestUsers(**req_kwargs)
    elif KeyboardButtonRequestUser is not None and "request_user" in _kb_params:
        btn_kwargs["request_user"] = KeyboardButtonRequestUser(
            request_id=101,
            user_is_bot=False,
        )
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(**btn_kwargs)],
            [KeyboardButton(**cancel_kwargs)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Нажмите «Выбрать пользователя» или введите @username / ID",
    )


def rebuild_markup_without_icons(markup: Any, strip_style: bool = False) -> Any:
    if isinstance(markup, ReplyKeyboardMarkup):
        return build_select_user_reply_kb(with_style_and_icons=False)
    if not isinstance(markup, InlineKeyboardMarkup):
        return markup
    new_rows: List[List[InlineKeyboardButton]] = []
    for row in markup.inline_keyboard:
        new_row: List[InlineKeyboardButton] = []
        for btn in row:
            style = None if strip_style else (
                getattr(btn, "style", None) or (getattr(btn, "api_kwargs", None) or {}).get("style")
            )
            new_row.append(
                make_btn(
                    text=btn.text,
                    callback_data=btn.callback_data,
                    url=btn.url,
                    style=style,
                    emoji_key=None,
                    with_icon=False,
                )
            )
        new_rows.append(new_row)
    return InlineKeyboardMarkup(new_rows)


async def safe_reply_text(message, text: str, reply_markup: Optional[Any] = None):
    try:
        return await message.reply_text(text, reply_markup=reply_markup)
    except BadRequest as e:
        err = str(e).lower()
        if reply_markup is not None and ("emoji" in err or "icon" in err or "style" in err):
            return await message.reply_text(
                text,
                reply_markup=rebuild_markup_without_icons(reply_markup, strip_style=("style" in err)),
            )
        raise


async def safe_reply_photo(message, photo, caption: str, reply_markup: Optional[Any] = None):
    try:
        return await message.reply_photo(photo=photo, caption=caption, reply_markup=reply_markup)
    except BadRequest as e:
        err = str(e).lower()
        if isinstance(reply_markup, InlineKeyboardMarkup) and ("emoji" in err or "icon" in err or "style" in err):
            if hasattr(photo, "seek"):
                photo.seek(0)
            return await message.reply_photo(
                photo=photo,
                caption=caption,
                reply_markup=rebuild_markup_without_icons(reply_markup, strip_style=("style" in err)),
            )
        raise


async def safe_send_message(bot, chat_id: int, text: str, reply_markup: Optional[Any] = None):
    try:
        return await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
    except BadRequest as e:
        err = str(e).lower()
        if reply_markup is not None and ("emoji" in err or "icon" in err or "style" in err):
            return await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=rebuild_markup_without_icons(reply_markup, strip_style=("style" in err)),
            )
        raise


async def animate_status_steps(
    status_msg,
    frames: List[str],
    delay: float = 0.35,
) -> None:
    """Плавная многокадровая анимация статуса без прерывания основного потока при ошибках."""
    if not status_msg or not frames:
        return
    for frame in frames:
        await asyncio.sleep(delay)
        try:
            await status_msg.edit_text(frame)
        except BadRequest as e:
            if "message is not modified" in str(e).lower():
                continue
            break
        except Exception:
            break


async def safe_edit_text(query, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
    if query.message and (query.message.photo or query.message.video or query.message.document):
        return await safe_reply_text(query.message, text, reply_markup=reply_markup)
    try:
        return await query.edit_message_text(text=text, reply_markup=reply_markup)
    except BadRequest as e:
        err = str(e).lower()
        if "message is not modified" in err:
            return None
        if "there is no text in the message" in err and query.message:
            return await safe_reply_text(query.message, text, reply_markup=reply_markup)
        if reply_markup and ("emoji" in err or "icon" in err or "style" in err):
            return await query.edit_message_text(
                text=text,
                reply_markup=rebuild_markup_without_icons(reply_markup, strip_style=("style" in err)),
            )
        raise


async def safe_edit_media_photo(query, photo, caption: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
    try:
        media = InputMediaPhoto(media=photo, caption=caption, parse_mode=ParseMode.HTML)
        return await query.edit_message_media(media=media, reply_markup=reply_markup)
    except BadRequest as e:
        err = str(e).lower()
        if "message is not modified" in err:
            return None
        if reply_markup and ("emoji" in err or "icon" in err or "style" in err):
            if hasattr(photo, "seek"):
                photo.seek(0)
            media = InputMediaPhoto(media=photo, caption=caption, parse_mode=ParseMode.HTML)
            return await query.edit_message_media(
                media=media,
                reply_markup=rebuild_markup_without_icons(reply_markup, strip_style=("style" in err)),
            )
        raise


async def safe_edit_reply_markup(query, reply_markup: Optional[InlineKeyboardMarkup] = None):
    try:
        return await query.edit_message_reply_markup(reply_markup=reply_markup)
    except BadRequest as e:
        err = str(e).lower()
        if "message is not modified" in err:
            return None
        if reply_markup and ("emoji" in err or "icon" in err or "style" in err):
            return await query.edit_message_reply_markup(
                reply_markup=rebuild_markup_without_icons(reply_markup, strip_style=("style" in err)),
            )
        raise


async def send_media_album_safe(
    bot,
    chat_id: int,
    media_items: List[Dict[str, str]],
    caption_prefix: str = "",
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> List[int]:
    """
    Отправляет прикреплённые фото и видео доказательства ВМЕСТЕ (альбомом send_media_group)
    пачками до 10 файлов (ограничение Telegram Bot API).
    """
    valid_items = [
        item for item in (media_items or [])
        if item.get("file_id") and item.get("type") in ("photo", "video")
    ]
    if not valid_items:
        return []

    sent_ids: List[int] = []
    chunks = [valid_items[i:i + 10] for i in range(0, len(valid_items), 10)]
    total_chunks = len(chunks)

    for chunk_idx, chunk in enumerate(chunks, start=1):
        chunk_cap = caption_prefix
        if chunk_cap and total_chunks > 1:
            chunk_cap = f"{caption_prefix} <code>(часть {chunk_idx}/{total_chunks})</code>"

        if len(chunk) == 1:
            item = chunk[0]
            single_rm = reply_markup if (total_chunks == 1) else None
            try:
                if item["type"] == "photo":
                    m = await bot.send_photo(
                        chat_id=chat_id,
                        photo=item["file_id"],
                        caption=chunk_cap or None,
                        parse_mode=ParseMode.HTML,
                        reply_markup=single_rm,
                    )
                else:
                    m = await bot.send_video(
                        chat_id=chat_id,
                        video=item["file_id"],
                        caption=chunk_cap or None,
                        parse_mode=ParseMode.HTML,
                        reply_markup=single_rm,
                    )
                sent_ids.append(m.message_id)
            except BadRequest as e:
                err_l = str(e).lower()
                if single_rm is not None and ("emoji" in err_l or "icon" in err_l or "style" in err_l):
                    try:
                        clean_rm = rebuild_markup_without_icons(single_rm, strip_style=("style" in err_l))
                        if item["type"] == "photo":
                            m = await bot.send_photo(
                                chat_id=chat_id,
                                photo=item["file_id"],
                                caption=chunk_cap or None,
                                parse_mode=ParseMode.HTML,
                                reply_markup=clean_rm,
                            )
                        else:
                            m = await bot.send_video(
                                chat_id=chat_id,
                                video=item["file_id"],
                                caption=chunk_cap or None,
                                parse_mode=ParseMode.HTML,
                                reply_markup=clean_rm,
                            )
                        sent_ids.append(m.message_id)
                        continue
                    except Exception as inner_e:
                        logger.warning("Фолбэк одиночного медиа не удался в %s: %s", chat_id, inner_e)
                else:
                    logger.warning("Ошибка одиночной отправки медиа в %s: %s", chat_id, e)
            except Exception as e:
                logger.warning("Ошибка одиночной отправки медиа в %s: %s", chat_id, e)
            continue

        group_media = []
        for idx, item in enumerate(chunk):
            cap = chunk_cap if idx == 0 and chunk_cap else None
            if item["type"] == "photo":
                group_media.append(
                    InputMediaPhoto(media=item["file_id"], caption=cap, parse_mode=ParseMode.HTML)
                )
            else:
                group_media.append(
                    InputMediaVideo(media=item["file_id"], caption=cap, parse_mode=ParseMode.HTML)
                )

        try:
            msgs = await bot.send_media_group(chat_id=chat_id, media=group_media)
            sent_ids.extend(m.message_id for m in msgs)
        except Exception as e:
            logger.warning("Ошибка send_media_group в %s (%s), пробую поштучный фолбэк", chat_id, e)
            for idx, item in enumerate(chunk):
                cap = chunk_cap if idx == 0 and chunk_cap else None
                try:
                    if item["type"] == "photo":
                        m = await bot.send_photo(
                            chat_id=chat_id,
                            photo=item["file_id"],
                            caption=cap,
                            parse_mode=ParseMode.HTML,
                        )
                    else:
                        m = await bot.send_video(
                            chat_id=chat_id,
                            video=item["file_id"],
                            caption=cap,
                            parse_mode=ParseMode.HTML,
                        )
                    sent_ids.append(m.message_id)
                except Exception as inner_e:
                    logger.warning("Фолбэк медиа не удался: %s", inner_e)

    return sent_ids


# =====================================================================
# HTML-ЭКРАНИРОВАНИЕ, ЦИТАТЫ И ЗАГРУЗКА ШРИФТОВ
# =====================================================================
def esc(text: Optional[str]) -> str:
    return html.escape(str(text or ""), quote=False)


def esc_attr(text: Optional[str]) -> str:
    return html.escape(str(text or ""), quote=True)


def clip_text(text: Optional[str], max_len: int) -> str:
    raw = str(text or "").strip()
    if len(raw) <= max_len:
        return raw
    return raw[: max(1, max_len - 1)].rstrip() + "…"


def quote_block(content: str, expandable: bool = False) -> str:
    if expandable:
        return f"<blockquote expandable>{content}</blockquote>"
    return f"<blockquote>{content}</blockquote>"


FONT_REGULAR_PATH = FONTS_DIR / "NotoSans-Regular.ttf"
FONT_BOLD_PATH = FONTS_DIR / "NotoSans-Bold.ttf"

SYSTEM_BOLD_CANDIDATES = [
    str(FONT_BOLD_PATH),
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]

SYSTEM_REGULAR_CANDIDATES = [
    str(FONT_REGULAR_PATH),
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


def _is_valid_ttf(data: bytes) -> bool:
    return len(data) > 4096 and data[:4] in (b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf")


def ensure_fonts_exist() -> None:
    downloads = [
        (
            FONT_REGULAR_PATH,
            "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf",
        ),
        (
            FONT_BOLD_PATH,
            "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Bold.ttf",
        ),
    ]
    for path, url in downloads:
        if path.exists() and _is_valid_ttf(path.read_bytes()):
            continue
        try:
            r = requests.get(url, timeout=12)
            if r.status_code == 200 and _is_valid_ttf(r.content):
                path.write_bytes(r.content)
        except Exception as e:
            logger.debug("Не удалось скачать шрифт %s: %s", path.name, e)


ensure_fonts_exist()


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = SYSTEM_BOLD_CANDIDATES if bold else SYSTEM_REGULAR_CANDIDATES
    for path_str in candidates:
        p = Path(path_str)
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def strip_all_emojis_for_image(
    text: Optional[str],
    fallback_username: Optional[str] = None,
    fallback_id: Optional[int] = None,
) -> str:
    emoji_pattern = re.compile(
        "["
        "\U00010000-\U0010FFFF"
        "\u200d"
        "\ufe0f"
        "\ufe0e"
        "\u2600-\u27bf"
        "\u2300-\u23ff"
        "\u2b50"
        "\u2b06"
        "\u2190-\u21ff"
        "\u2934-\u2935"
        "\u3297"
        "\u3299"
        "\u3030"
        "\u00a9"
        "\u00ae"
        "]+",
        flags=re.UNICODE,
    )

    def _clean(raw: str) -> str:
        cleaned = emoji_pattern.sub("", raw)
        res = []
        for char in unicodedata.normalize("NFKC", cleaned):
            cat = unicodedata.category(char)
            if cat in ("So", "Cn", "Co", "Sk", "Cs", "Cf"):
                continue
            code = ord(char)
            if (
                0x0020 <= code <= 0x024F
                or 0x0400 <= code <= 0x04FF
                or char in ("_", "-", ".", "@", "#", " ", "№", ":", "/", "(", ")", "!", "?", ",", "+", "•")
            ):
                res.append(char)
        return re.sub(r"\s+", " ", "".join(res)).strip()

    if text:
        cleaned_main = _clean(str(text))
        if cleaned_main and cleaned_main.lower() not in {"unknown", "none", "null"}:
            return cleaned_main

    if fallback_username:
        uname_clean = _clean(str(fallback_username).lstrip("@"))
        if uname_clean:
            return f"@{uname_clean}"

    if fallback_id is not None:
        return f"ID {fallback_id}"

    return "User"


def fit_text_width(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    if not text:
        return ""
    if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
        return text
    trimmed = text
    while len(trimmed) > 2 and draw.textbbox((0, 0), trimmed + "...", font=font)[2] > max_width:
        trimmed = trimmed[:-1]
    return trimmed.rstrip() + "..."


def wrap_text_for_image(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int = 2) -> List[str]:
    words = text.split()
    if not words:
        return ["Не указано"]

    lines: List[str] = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
                current_line = word
            else:
                lines.append(fit_text_width(draw, word, font, max_width))
                current_line = ""

            if len(lines) >= max_lines:
                break

    if current_line and len(lines) < max_lines:
        lines.append(current_line)

    if len(lines) == max_lines:
        joined = " ".join(lines)
        if len(joined) < len(" ".join(words)):
            lines[-1] = fit_text_width(draw, lines[-1], font, max_width)

    return lines


# =====================================================================
# НАСТОЯЩЕЕ ЖИДКОЕ СТЕКЛО (APPLE LIQUID GLASS ENGINE) И ЧИСТЫЕ КАРТОЧКИ
# =====================================================================
def make_smooth_rounded_mask(width: int, height: int, radius: int) -> Image.Image:
    scale = 2
    big = Image.new("L", (width * scale, height * scale), 0)
    bdraw = ImageDraw.Draw(big)
    bdraw.rounded_rectangle(
        [0, 0, width * scale - 1, height * scale - 1],
        radius=radius * scale,
        fill=255,
    )
    return big.resize((width, height), Image.Resampling.LANCZOS)


def make_calm_tonal_backdrop(
    width: int,
    height: int,
    base_rgb: Tuple[int, int, int],
    highlight_rgb: Tuple[int, int, int],
    deep_rgb: Tuple[int, int, int],
) -> Image.Image:
    """
    Спокойный однородный по цвету фон с мягкими световыми волнами в той же палитре,
    благодаря которым преломление и глянец жидкого стекла видны чётко и объёмно.
    """
    img = Image.new("RGBA", (width, height), (*base_rgb, 255))

    grad = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(grad)
    for y in range(height):
        t = y / max(1, height - 1)
        r = int(base_rgb[0] * (1 - t) + deep_rgb[0] * t)
        g = int(base_rgb[1] * (1 - t) + deep_rgb[1] * t)
        b = int(base_rgb[2] * (1 - t) + deep_rgb[2] * t)
        g_draw.line([(0, y), (width, y)], fill=(r, g, b, 255))
    img = Image.alpha_composite(img, grad)

    # Плавная световая волна под стеклом (даёт заметное оптическое преломление внутри стекла без рамок)
    light_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    l_draw = ImageDraw.Draw(light_layer)
    l_draw.ellipse(
        [-int(width * 0.12), -int(height * 0.35), int(width * 0.56), int(height * 0.82)],
        fill=(*highlight_rgb, 150),
    )
    l_draw.ellipse(
        [int(width * 0.46), int(height * 0.22), int(width * 1.12), int(height * 1.28)],
        fill=(*highlight_rgb, 115),
    )
    l_draw.polygon(
        [
            (int(width * 0.04), int(height * 0.88)),
            (int(width * 0.42), 0),
            (int(width * 0.64), 0),
            (int(width * 0.24), height),
        ],
        fill=(*highlight_rgb, 72),
    )
    light_layer = light_layer.filter(ImageFilter.GaussianBlur(62))
    img = Image.alpha_composite(img, light_layer)
    return img


def _refract_glass_lens(
    base_img: Image.Image,
    box: Tuple[int, int, int, int],
    refract_px: int = 12,
) -> Image.Image:
    """
    Оптическое преломление изогнутых краёв толстого жидкого стекла (5x5 MESH-линза).
    """
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    bw, bh = base_img.size

    pad = min(24, max(8, refract_px + 6))
    cx1 = max(0, x1 - pad)
    cy1 = max(0, y1 - pad)
    cx2 = min(bw, x2 + pad)
    cy2 = min(bh, y2 + pad)

    src = base_img.crop((cx1, cy1, cx2, cy2))
    ox = x1 - cx1
    oy = y1 - cy1

    ex1 = max(4, min(int(w * 0.09), 28))
    ex2 = max(ex1 + 4, min(int(w * 0.23), 76))
    ey1 = max(4, min(int(h * 0.11), 28))
    ey2 = max(ey1 + 4, min(int(h * 0.26), 72))

    if w <= ex2 * 2 + 8 or h <= ey2 * 2 + 8:
        return base_img.crop((x1, y1, x2, y2))

    rx = min(refract_px, pad, ex1 - 1)
    ry = min(refract_px, pad, ey1 - 1)

    dst_xs = [0, ex1, ex2, w - ex2, w - ex1, w]
    dst_ys = [0, ey1, ey2, h - ey2, h - ey1, h]

    src_xs = [ox - rx, ox + int(ex1 * 0.62), ox + ex2, ox + w - ex2, ox + w - int(ex1 * 0.62), ox + w + rx]
    src_ys = [oy - ry, oy + int(ey1 * 0.62), oy + ey2, oy + h - ey2, oy + h - int(ey1 * 0.62), oy + h + ry]

    mesh = []
    for row in range(5):
        for col in range(5):
            target_bbox = (dst_xs[col], dst_ys[row], dst_xs[col + 1], dst_ys[row + 1])
            nw = (src_xs[col], src_ys[row])
            sw = (src_xs[col], src_ys[row + 1])
            se = (src_xs[col + 1], src_ys[row + 1])
            ne = (src_xs[col + 1], src_ys[row])
            source_quad = (nw[0], nw[1], sw[0], sw[1], se[0], se[1], ne[0], ne[1])
            mesh.append((target_bbox, source_quad))

    return src.transform((w, h), Image.Transform.MESH, mesh, resample=Image.Resampling.BICUBIC)


def draw_liquid_glass_panel(
    base_img: Image.Image,
    box: Tuple[int, int, int, int],
    radius: int = 38,
    tint_color: Tuple[int, int, int, int] = (255, 255, 255, 20),
    border_highlight: Tuple[int, int, int, int] = (255, 255, 255, 0),
    border_shadow: Tuple[int, int, int, int] = (255, 255, 255, 0),
    blur_radius: int = 18,
    refract_px: int = 12,
) -> None:
    """
    Чистое бесшовное жидкое стекло (Borderless Liquid Glass) без рамок и обводок:
    - Мягкая парящая глубина и контактная тень
    - Оптическое преломление по краю линзы (5x5 MESH)
    - Матовое размытие + подъём цвета и мягкий световой мениск без жёстких контуров
    """
    _ = border_highlight, border_shadow
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    if w <= 10 or h <= 10:
        return

    # 1. Мягкая парящая глубина без видимой кромки
    shadow_pad = 32
    shadow_layer = Image.new("RGBA", (w + shadow_pad * 2, h + shadow_pad * 2), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow_layer)
    s_draw.rounded_rectangle(
        [shadow_pad, shadow_pad + 10, shadow_pad + w - 1, shadow_pad + h + 9],
        radius=radius,
        fill=(0, 0, 0, 92),
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(20))
    base_img.alpha_composite(shadow_layer, (x1 - shadow_pad, y1 - shadow_pad))

    # 2. Преломление + матовый слой + чистая оптическая глубина
    refracted = _refract_glass_lens(base_img, box, refract_px=refract_px)
    frosted = refracted.filter(ImageFilter.GaussianBlur(blur_radius))
    frosted = ImageEnhance.Color(frosted).enhance(1.22)
    frosted = ImageEnhance.Brightness(frosted).enhance(1.10)

    tint_overlay = Image.new("RGBA", (w, h), tint_color)
    glass_body = Image.alpha_composite(frosted, tint_overlay)

    # 3. Внутренние плавные переливы света (верхний мениск, диагональное свечение, нижний блик)
    optics = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    o_draw = ImageDraw.Draw(optics)

    meniscus_h = max(1, int(h * 0.42))
    for row in range(meniscus_h):
        t = 1.0 - (row / meniscus_h)
        alpha = int(42 * (t ** 2.3))
        if alpha > 0:
            o_draw.line([(0, row), (w, row)], fill=(255, 255, 255, alpha))

    o_draw.polygon(
        [
            (int(w * 0.05), 0),
            (int(w * 0.28), 0),
            (int(w * 0.06), h),
            (-int(w * 0.08), h),
        ],
        fill=(255, 255, 255, 22),
    )

    caustic_h = max(1, int(h * 0.16))
    for idx in range(caustic_h):
        t = idx / max(1, caustic_h - 1)
        alpha = int(18 * (t ** 2.1))
        if alpha > 0:
            y_pos = h - caustic_h + idx
            o_draw.line([(0, y_pos), (w, y_pos)], fill=(255, 255, 255, alpha))

    optics = optics.filter(ImageFilter.GaussianBlur(10))
    glass_body = Image.alpha_composite(glass_body, optics)

    mask = make_smooth_rounded_mask(w, h, radius)
    base_img.paste(glass_body, (x1, y1), mask)


def make_default_avatar(size: int = 208, text: str = "USER", theme: str = "unverified") -> Image.Image:
    palettes = {
        "scammer": ((118, 36, 48, 255), "SC"),
        "guarantor": ((28, 96, 66, 255), "GR"),
        "unverified": ((34, 68, 128, 255), "ID"),
    }
    bg_col, default_init = palettes.get(theme, palettes["unverified"])

    img = Image.new("RGBA", (size, size), bg_col)
    draw = ImageDraw.Draw(img)

    clean_txt = strip_all_emojis_for_image(text).lstrip("@").strip()
    initials = clean_txt[:2].upper() if clean_txt else default_init
    font = load_font(int(size * 0.36), bold=True)
    draw.text((size // 2, size // 2), initials, font=font, fill=(255, 255, 255, 255), anchor="mm")
    return img


def _prepare_avatar(
    avatar_bytes: Optional[bytes],
    size: int,
    fallback_name: str,
    theme: str,
) -> Image.Image:
    if avatar_bytes:
        try:
            loaded = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            return ImageOps.fit(loaded, (size, size), method=Image.Resampling.LANCZOS)
        except Exception:
            pass
    return make_default_avatar(size, fallback_name, theme=theme)


def _paste_avatar_with_glass_bezel(
    img: Image.Image,
    av_img: Image.Image,
    pos: Tuple[int, int],
    radius: int,
    border_color: Optional[Tuple[int, int, int, int]] = None,
) -> None:
    _ = border_color
    x, y = pos
    w, h = av_img.size

    sh = Image.new("RGBA", (w + 24, h + 24), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.rounded_rectangle([12, 16, 12 + w - 1, 16 + h - 1], radius=radius, fill=(0, 0, 0, 96))
    sh = sh.filter(ImageFilter.GaussianBlur(10))
    img.alpha_composite(sh, (x - 12, y - 12))

    mask = make_smooth_rounded_mask(w, h, radius)
    img.paste(av_img, (x, y), mask)


async def generate_main_menu_card_image() -> io.BytesIO:
    """
    Чистая минималистичная Liquid Glass карточка главного меню без рамок и обводок.
    """
    WIDTH, HEIGHT = 1000, 340
    img = make_calm_tonal_backdrop(
        WIDTH,
        HEIGHT,
        base_rgb=(22, 34, 58),
        highlight_rgb=(70, 108, 174),
        deep_rgb=(13, 21, 38),
    )

    draw_liquid_glass_panel(
        img,
        (56, 44, WIDTH - 56, HEIGHT - 44),
        radius=42,
        tint_color=(165, 200, 255, 20),
        blur_radius=18,
        refract_px=12,
    )

    draw = ImageDraw.Draw(img)
    draw.text((WIDTH // 2, 142), BOT_NAME, font=load_font(64, bold=True), fill=(255, 255, 255), anchor="mm")
    draw.text((WIDTH // 2, 220), "Антискам-бот", font=load_font(28, bold=False), fill=(235, 242, 255), anchor="mm")

    bio = io.BytesIO()
    img.convert("RGB").save(bio, "PNG")
    bio.name = "main_menu.png"
    bio.seek(0)
    return bio


async def generate_unverified_card_image(
    target_user_id: Optional[int],
    username: str,
    full_name: str,
    avatar_bytes: Optional[bytes] = None,
) -> io.BytesIO:
    """
    Тёмно-синяя Liquid Glass карточка «НЕПРОВЕРЕННЫЙ» без рамок, обводок и с чётким белым текстом.
    """
    WIDTH, HEIGHT = 1000, 380
    img = make_calm_tonal_backdrop(
        WIDTH,
        HEIGHT,
        base_rgb=(18, 42, 86),
        highlight_rgb=(54, 110, 192),
        deep_rgb=(11, 26, 56),
    )

    draw_liquid_glass_panel(
        img,
        (40, 34, WIDTH - 40, HEIGHT - 34),
        radius=38,
        tint_color=(110, 168, 250, 22),
        blur_radius=18,
        refract_px=12,
    )

    av_size = 208
    clean_name = strip_all_emojis_for_image(full_name, fallback_username=username, fallback_id=target_user_id)
    av_img = _prepare_avatar(avatar_bytes, av_size, clean_name, theme="unverified")
    _paste_avatar_with_glass_bezel(img, av_img, (76, 86), radius=30)

    draw = ImageDraw.Draw(img)
    text_x = 320
    draw.text((text_x, 82), "НЕПРОВЕРЕННЫЙ", font=load_font(38, bold=True), fill=(255, 255, 255))

    name_font = load_font(35, bold=True)
    draw.text((text_x, 144), fit_text_width(draw, clean_name, name_font, 595), font=name_font, fill=(255, 255, 255))

    uname_disp = f"@{username.lstrip('@')}" if username else "Нет username"
    id_disp = f"ID: {target_user_id}" if target_user_id else "ID: Неизвестен"
    meta_font = load_font(24, bold=True)
    draw.text((text_x, 200), fit_text_width(draw, f"{uname_disp}  •  {id_disp}", meta_font, 595), font=meta_font, fill=(235, 243, 255))

    draw.text((text_x, 262), "Нет в базе скамеров и гарантов", font=load_font(22, bold=False), fill=(230, 240, 255))

    bio = io.BytesIO()
    img.convert("RGB").save(bio, "PNG")
    bio.name = f"unverified_{target_user_id or 'card'}.png"
    bio.seek(0)
    return bio


async def generate_scammer_card_image(
    target_user_id: Optional[int],
    username: str,
    full_name: str,
    reason: str,
    damage: str,
    added_at: str,
    case_id: int,
    avatar_bytes: Optional[bytes] = None,
) -> io.BytesIO:
    """
    Выраженная красная Liquid Glass карточка «СКАМЕР» без рамок, обводок и с чётким белым текстом.
    """
    WIDTH, HEIGHT = 1000, 410
    img = make_calm_tonal_backdrop(
        WIDTH,
        HEIGHT,
        base_rgb=(74, 21, 30),
        highlight_rgb=(152, 46, 62),
        deep_rgb=(46, 12, 19),
    )

    draw_liquid_glass_panel(
        img,
        (40, 34, WIDTH - 40, HEIGHT - 34),
        radius=38,
        tint_color=(220, 88, 102, 20),
        blur_radius=18,
        refract_px=12,
    )

    av_size = 208
    clean_name = strip_all_emojis_for_image(full_name, fallback_username=username, fallback_id=target_user_id)
    av_img = _prepare_avatar(avatar_bytes, av_size, clean_name, theme="scammer")
    _paste_avatar_with_glass_bezel(img, av_img, (76, 101), radius=30)

    draw = ImageDraw.Draw(img)
    text_x = 320
    draw.text((text_x, 68), f"СКАМЕР  •  #{case_id}", font=load_font(38, bold=True), fill=(255, 255, 255))

    name_font = load_font(35, bold=True)
    draw.text((text_x, 126), fit_text_width(draw, clean_name, name_font, 595), font=name_font, fill=(255, 255, 255))

    uname_disp = f"@{username.lstrip('@')}" if username else "Нет username"
    id_disp = f"ID: {target_user_id}" if target_user_id else "ID: Неизвестен"
    meta_font = load_font(23, bold=True)
    draw.text((text_x, 180), fit_text_width(draw, f"{uname_disp}  •  {id_disp}", meta_font, 595), font=meta_font, fill=(248, 236, 238))

    clean_damage = strip_all_emojis_for_image(damage or "Подтверждённый скам")
    dmg_font = load_font(23, bold=True)
    draw.text((text_x, 232), fit_text_width(draw, f"Ущерб: {clean_damage}", dmg_font, 595), font=dmg_font, fill=(255, 255, 255))

    clean_reason = strip_all_emojis_for_image(reason or "Мошенничество при сделке")
    body_font = load_font(21, bold=False)
    reason_lines = wrap_text_for_image(draw, clean_reason, body_font, max_width=595, max_lines=2)
    for idx, line in enumerate(reason_lines):
        draw.text((text_x, 274 + idx * 30), line, font=body_font, fill=(248, 238, 240))

    bio = io.BytesIO()
    img.convert("RGB").save(bio, "PNG")
    bio.name = f"scammer_{target_user_id or 'card'}.png"
    bio.seek(0)
    return bio


async def generate_guarantor_card_image(
    target_user_id: Optional[int],
    username: str,
    full_name: str,
    note: str,
    added_at: str,
    guar_id: int,
    avatar_bytes: Optional[bytes] = None,
) -> io.BytesIO:
    """
    Выраженная зелёная Liquid Glass карточка «ГАРАНТ» без рамок, обводок и с чётким белым текстом.
    """
    WIDTH, HEIGHT = 1000, 380
    img = make_calm_tonal_backdrop(
        WIDTH,
        HEIGHT,
        base_rgb=(16, 60, 42),
        highlight_rgb=(44, 138, 94),
        deep_rgb=(10, 38, 26),
    )

    draw_liquid_glass_panel(
        img,
        (40, 34, WIDTH - 40, HEIGHT - 34),
        radius=38,
        tint_color=(90, 200, 142, 20),
        blur_radius=18,
        refract_px=12,
    )

    av_size = 208
    clean_name = strip_all_emojis_for_image(full_name, fallback_username=username, fallback_id=target_user_id)
    av_img = _prepare_avatar(avatar_bytes, av_size, clean_name, theme="guarantor")
    _paste_avatar_with_glass_bezel(img, av_img, (76, 86), radius=30)

    draw = ImageDraw.Draw(img)
    text_x = 320
    draw.text((text_x, 82), f"ГАРАНТ  •  #{guar_id}", font=load_font(38, bold=True), fill=(255, 255, 255))

    name_font = load_font(35, bold=True)
    draw.text((text_x, 144), fit_text_width(draw, clean_name, name_font, 595), font=name_font, fill=(255, 255, 255))

    uname_disp = f"@{username.lstrip('@')}" if username else "Нет username"
    id_disp = f"ID: {target_user_id}" if target_user_id else "ID: Неизвестен"
    meta_font = load_font(24, bold=True)
    draw.text((text_x, 200), fit_text_width(draw, f"{uname_disp}  •  {id_disp}", meta_font, 595), font=meta_font, fill=(236, 250, 242))

    clean_note = strip_all_emojis_for_image(note or "Официальный проверенный гарант")
    note_font = load_font(22, bold=False)
    draw.text((text_x, 262), fit_text_width(draw, clean_note, note_font, 595), font=note_font, fill=(236, 250, 242))

    bio = io.BytesIO()
    img.convert("RGB").save(bio, "PNG")
    bio.name = f"guarantor_{target_user_id or 'card'}.png"
    bio.seek(0)
    return bio


# =====================================================================
# БАЗА ДАННЫХ (SQLITE + FIREBASE SYNC)
# =====================================================================
def db_connect(write: bool = False) -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout = 5000;")
    except Exception:
        pass
    if write:
        firebase_manager.schedule_sync()
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    with db_connect(write=False) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scammers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                username TEXT DEFAULT '',
                extra_usernames TEXT DEFAULT '',
                full_name TEXT DEFAULT '',
                reason TEXT NOT NULL,
                proof TEXT DEFAULT '',
                proof_url TEXT DEFAULT '',
                proof_media_json TEXT DEFAULT '[]',
                damage TEXT DEFAULT '',
                added_by INTEGER NOT NULL,
                added_at TEXT NOT NULL
            )
        """)
        _ensure_column(conn, "scammers", "extra_usernames", "TEXT DEFAULT ''")
        _ensure_column(conn, "scammers", "proof_url", "TEXT DEFAULT ''")
        _ensure_column(conn, "scammers", "proof_media_json", "TEXT DEFAULT '[]'")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_scammers_username ON scammers(username);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_scammers_user_id ON scammers(user_id);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS guarantors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                username TEXT DEFAULT '',
                extra_usernames TEXT DEFAULT '',
                full_name TEXT DEFAULT '',
                note TEXT DEFAULT '',
                proof_url TEXT DEFAULT '',
                added_by INTEGER NOT NULL,
                added_at TEXT NOT NULL
            )
        """)
        _ensure_column(conn, "guarantors", "extra_usernames", "TEXT DEFAULT ''")
        _ensure_column(conn, "guarantors", "proof_url", "TEXT DEFAULT ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_guarantors_username ON guarantors(username);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_guarantors_user_id ON guarantors(user_id);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users_cache (
                user_id INTEGER PRIMARY KEY,
                username TEXT DEFAULT '',
                extra_usernames TEXT DEFAULT '',
                full_name TEXT DEFAULT '',
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ucache_username ON users_cache(username);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_key TEXT NOT NULL,
                voter_id INTEGER NOT NULL,
                vote_type TEXT NOT NULL CHECK(vote_type IN ('like', 'dislike')),
                voted_at TEXT NOT NULL,
                UNIQUE(target_key, voter_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_votes_target ON user_votes(target_key);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS check_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checker_id INTEGER NOT NULL,
                query_text TEXT NOT NULL,
                is_scammer INTEGER NOT NULL DEFAULT 0,
                result_type TEXT DEFAULT 'unverified',
                checked_at TEXT NOT NULL
            )
        """)
        _ensure_column(conn, "check_logs", "result_type", "TEXT DEFAULT 'unverified'")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS scam_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reporter_id INTEGER NOT NULL,
                reporter_username TEXT DEFAULT '',
                reporter_name TEXT DEFAULT '',
                target_id INTEGER,
                target_username TEXT DEFAULT '',
                target_name TEXT DEFAULT '',
                description TEXT NOT NULL,
                media_json TEXT DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'pending',
                assigned_admin_id INTEGER,
                assigned_at REAL DEFAULT 0,
                admin_msg_ids_json TEXT DEFAULT '[]',
                decision_by INTEGER,
                reject_reason TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_status ON scam_reports(status);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS moderators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                username TEXT DEFAULT '',
                full_name TEXT DEFAULT '',
                added_by INTEGER NOT NULL,
                added_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_moderators_uid ON moderators(user_id);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT DEFAULT ''
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_agreements (
                user_id INTEGER PRIMARY KEY,
                accepted_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_started_users (
                user_id INTEGER PRIMARY KEY,
                username TEXT DEFAULT '',
                full_name TEXT DEFAULT '',
                started_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            INSERT OR IGNORE INTO bot_started_users (user_id, username, full_name, started_at)
            SELECT ua.user_id,
                   COALESCE(uc.username, ''),
                   COALESCE(uc.full_name, ''),
                   ua.accepted_at
            FROM user_agreements ua
            LEFT JOIN users_cache uc ON uc.user_id = ua.user_id
        """)

        # Восстанавливаем недостающие user_id из текста пруфов/жалоб и users_cache
        for tbl in ("scammers", "guarantors"):
            extra_cols = ", reason, proof, proof_url" if tbl == "scammers" else ""
            null_rows = conn.execute(
                f"SELECT id, username, extra_usernames{extra_cols} FROM {tbl} WHERE user_id IS NULL"
            ).fetchall()
            for nr in null_rows:
                cand_uid: Optional[int] = None
                un_low = (nr["username"] or "").strip().lstrip("@").lower()
                if un_low:
                    uc_r = conn.execute("SELECT user_id FROM users_cache WHERE LOWER(username)=?", (un_low,)).fetchone()
                    if uc_r and uc_r["user_id"]:
                        cand_uid = int(uc_r["user_id"])
                if not cand_uid and tbl == "scammers":
                    txt_pool = f"{nr['proof'] or ''}\n{nr['reason'] or ''}\n{nr['proof_url'] or ''}"
                    cand_uid = _extract_uid_from_text(txt_pool)
                if cand_uid:
                    taken = conn.execute(f"SELECT id FROM {tbl} WHERE user_id=?", (cand_uid,)).fetchone()
                    if not taken:
                        conn.execute(f"UPDATE {tbl} SET user_id=? WHERE id=?", (cand_uid, int(nr["id"])))

        conn.commit()


def _serialize_extra_usernames(extra_usernames: Optional[List[str]]) -> str:
    if not extra_usernames:
        return ""
    cleaned = []
    seen = set()
    for u in extra_usernames:
        u_clean = (u or "").strip().lstrip("@").lower()
        if u_clean and u_clean not in seen:
            seen.add(u_clean)
            cleaned.append(u_clean)
    return ",".join(cleaned)


def _parse_extra_usernames(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [u.strip().lstrip("@") for u in raw.split(",") if u.strip()]


def _merge_username_aliases(primary: str, *sources: Any) -> List[str]:
    """Собирает единый список дополнительных/предыдущих юзернеймов без дублей и без primary."""
    primary_low = (primary or "").strip().lstrip("@").lower()
    seen = {primary_low} if primary_low else set()
    merged: List[str] = []

    def _push(val: str) -> None:
        u_clean = (val or "").strip().lstrip("@").lower()
        if u_clean and u_clean not in seen:
            seen.add(u_clean)
            merged.append(u_clean)

    for src in sources:
        if not src:
            continue
        if isinstance(src, str):
            for part in src.split(","):
                _push(part)
        elif isinstance(src, (list, tuple, set)):
            for item in src:
                if item:
                    for part in str(item).split(","):
                        _push(part)
    return merged


def _is_placeholder_name(name: str, username: str = "", user_id: Optional[int] = None) -> bool:
    n = (name or "").strip()
    if not n:
        return True
    n_low = n.lower()
    if username and n_low == f"@{username.strip().lstrip('@').lower()}":
        return True
    if user_id and n_low == f"id {int(user_id)}":
        return True
    if n_low.startswith("id ") and n_low[3:].strip().isdigit():
        return True
    return False


def _parse_media_json(raw: Optional[str]) -> List[Dict[str, str]]:
    if not raw:
        return []
    try:
        items = json.loads(raw)
        if isinstance(items, list):
            return [m for m in items if isinstance(m, dict) and m.get("file_id")]
    except Exception:
        pass
    return []


def db_upsert_user_cache(
    user_id: Optional[int],
    username: str = "",
    extra_usernames: Optional[List[str]] = None,
    full_name: str = "",
) -> None:
    if not user_id or int(user_id) <= 0:
        return
    uid = int(user_id)
    uname_clean = (username or "").strip().lstrip("@").lower()
    clean_name = (full_name or "").strip()

    with db_connect(write=False) as rconn:
        existing = rconn.execute("SELECT * FROM users_cache WHERE user_id=?", (uid,)).fetchone()

    if existing:
        old_uname = (existing["username"] or "").strip().lstrip("@").lower()
        old_extras = existing["extra_usernames"] or ""
        old_name = (existing["full_name"] or "").strip()

        final_uname = uname_clean or old_uname
        extra_sources: List[Any] = [old_extras, extra_usernames or []]
        if old_uname and final_uname and old_uname != final_uname:
            extra_sources.insert(0, old_uname)
        merged_extras = _merge_username_aliases(final_uname, *extra_sources)
        final_extra_str = _serialize_extra_usernames(merged_extras)

        if clean_name and (not _is_placeholder_name(clean_name, final_uname, uid) or not old_name):
            final_name = clean_name
        else:
            final_name = old_name or clean_name

        if final_uname == old_uname and final_extra_str == old_extras and final_name == old_name:
            return
    else:
        final_uname = uname_clean
        final_extra_str = _serialize_extra_usernames(_merge_username_aliases(final_uname, extra_usernames or []))
        final_name = clean_name

    now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    with db_connect(write=True) as conn:
        conn.execute(
            """
            INSERT INTO users_cache (user_id, username, extra_usernames, full_name, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                extra_usernames = excluded.extra_usernames,
                full_name = CASE WHEN excluded.full_name != '' THEN excluded.full_name ELSE users_cache.full_name END,
                updated_at = excluded.updated_at
            """,
            (uid, final_uname, final_extra_str, final_name, now_str),
        )
        conn.commit()


def db_get_user_cache(user_id: Optional[int] = None, username: str = "") -> Optional[sqlite3.Row]:
    uname_clean = (username or "").strip().lstrip("@").lower()
    with db_connect(write=False) as conn:
        if user_id and int(user_id) > 0:
            row = conn.execute("SELECT * FROM users_cache WHERE user_id=?", (int(user_id),)).fetchone()
            if row:
                return row
        if uname_clean:
            row = conn.execute("SELECT * FROM users_cache WHERE LOWER(username)=?", (uname_clean,)).fetchone()
            if row:
                return row
            candidates = conn.execute("SELECT * FROM users_cache WHERE extra_usernames != ''").fetchall()
            for r in candidates:
                if uname_clean in [u.lower() for u in _parse_extra_usernames(r["extra_usernames"])]:
                    return r
    return None


def _extract_uid_from_text(text: Optional[str]) -> Optional[int]:
    """Извлекает числовой личный Telegram ID из текста или HTML (ссылки tg://, ID: ..., @123456)."""
    if not text:
        return None
    raw = html.unescape(str(text))
    patterns = (
        r"tg://[A-Za-z0-9_]+\?(?:[^#\s\"'<]*&)?(?:user_id|chat_id|id)=(\d{5,14})(?:\b|$)",
        r"https?://(?:t\.me|telegram\.me)/@?(?:id)?(\d{5,14})(?:[/?#\s\"'<]|$)",
        r"https?://web\.telegram\.org/[a-z]/#(\d{5,14})(?:\b|$)",
        r"(?:^|[\s(>])(?:tg\s*id|uid|айди|идентификатор|\bid\b|🆔)\s*[:=#-]?\s*(\d{5,14})(?:\b|$)",
        r"(?:^|\s)[@#](?:id)?(\d{5,14})(?:\b|$)",
    )
    for pat in patterns:
        for m in re.finditer(pat, raw, flags=re.IGNORECASE):
            try:
                val = int(m.group(1))
                if 10000 <= val <= 9999999999999:
                    return val
            except (TypeError, ValueError):
                continue
    return None


def db_lookup_known_identity(
    user_id: Optional[int] = None,
    username: str = "",
    extra_usernames: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Кросс-поиск связки Telegram ID <-> username во всех таблицах базы:
    users_cache, scammers, guarantors, moderators, scam_reports (включая ID в тексте пруфов/жалоб).
    """
    uid = int(user_id) if user_id and int(user_id) > 0 else None
    uname_clean = (username or "").strip().lstrip("@").lower()
    search_unames = _merge_username_aliases("", [uname_clean] if uname_clean else [], extra_usernames or [])

    found = False
    best_uid = uid
    primary_candidates: List[str] = []
    alias_sources: List[Any] = []
    name_candidates: List[str] = []

    def _collect(r_uid: Any, r_un: Any, r_ex: Any, r_name: Any, fallback_text: str = "") -> None:
        nonlocal found, best_uid
        found = True
        if r_uid and int(r_uid) > 0 and not best_uid:
            best_uid = int(r_uid)
        elif not best_uid and fallback_text:
            ext_uid = _extract_uid_from_text(fallback_text)
            if ext_uid:
                best_uid = ext_uid
        un_c = (r_un or "").strip().lstrip("@").lower()
        if un_c:
            primary_candidates.append(un_c)
            alias_sources.append(un_c)
        if r_ex:
            alias_sources.append(r_ex)
        nm_c = (r_name or "").strip()
        if nm_c:
            name_candidates.append(nm_c)

    def _scan_table_by_uid(conn: sqlite3.Connection, target_uid: int) -> None:
        r = conn.execute("SELECT user_id, username, extra_usernames, full_name FROM users_cache WHERE user_id=?", (target_uid,)).fetchone()
        if r:
            _collect(r["user_id"], r["username"], r["extra_usernames"], r["full_name"])
        r = conn.execute("SELECT user_id, username, extra_usernames, full_name FROM guarantors WHERE user_id=?", (target_uid,)).fetchone()
        if r:
            _collect(r["user_id"], r["username"], r["extra_usernames"], r["full_name"])
        r = conn.execute("SELECT user_id, username, extra_usernames, full_name FROM scammers WHERE user_id=?", (target_uid,)).fetchone()
        if r:
            _collect(r["user_id"], r["username"], r["extra_usernames"], r["full_name"])
        r = conn.execute("SELECT user_id, username, full_name FROM moderators WHERE user_id=?", (target_uid,)).fetchone()
        if r:
            _collect(r["user_id"], r["username"], "", r["full_name"])
        for r in conn.execute(
            "SELECT target_id, target_username, target_name FROM scam_reports WHERE target_id=? ORDER BY id DESC LIMIT 3",
            (target_uid,),
        ).fetchall():
            _collect(r["target_id"], r["target_username"], "", r["target_name"])
        for r in conn.execute(
            "SELECT reporter_id, reporter_username, reporter_name FROM scam_reports WHERE reporter_id=? ORDER BY id DESC LIMIT 3",
            (target_uid,),
        ).fetchall():
            _collect(r["reporter_id"], r["reporter_username"], "", r["reporter_name"])

    def _scan_table_by_unames(conn: sqlite3.Connection, cand_unames: List[str]) -> None:
        if not cand_unames:
            return
        cand_set = set(cand_unames)
        for un in cand_unames:
            r = conn.execute("SELECT user_id, username, extra_usernames, full_name FROM users_cache WHERE LOWER(username)=?", (un,)).fetchone()
            if r:
                _collect(r["user_id"], r["username"], r["extra_usernames"], r["full_name"])
            r = conn.execute("SELECT user_id, username, extra_usernames, full_name FROM guarantors WHERE LOWER(username)=?", (un,)).fetchone()
            if r:
                _collect(r["user_id"], r["username"], r["extra_usernames"], r["full_name"])
            r = conn.execute(
                "SELECT user_id, username, extra_usernames, full_name, reason, proof, proof_url FROM scammers WHERE LOWER(username)=?",
                (un,),
            ).fetchone()
            if r:
                fb_txt = f"{r['proof'] or ''}\n{r['reason'] or ''}\n{r['proof_url'] or ''}"
                _collect(r["user_id"], r["username"], r["extra_usernames"], r["full_name"], fallback_text=fb_txt)
            r = conn.execute("SELECT user_id, username, full_name FROM moderators WHERE LOWER(username)=?", (un,)).fetchone()
            if r:
                _collect(r["user_id"], r["username"], "", r["full_name"])
            for r in conn.execute(
                "SELECT target_id, target_username, target_name, description FROM scam_reports WHERE LOWER(target_username)=? ORDER BY id DESC LIMIT 3",
                (un,),
            ).fetchall():
                _collect(r["target_id"], r["target_username"], "", r["target_name"], fallback_text=r["description"] or "")
            for r in conn.execute(
                "SELECT reporter_id, reporter_username, reporter_name FROM scam_reports WHERE LOWER(reporter_username)=? ORDER BY id DESC LIMIT 3",
                (un,),
            ).fetchall():
                _collect(r["reporter_id"], r["reporter_username"], "", r["reporter_name"])

        for tbl in ("users_cache", "guarantors", "scammers"):
            extra_cols = ", reason, proof, proof_url" if tbl == "scammers" else ""
            rows = conn.execute(
                f"SELECT user_id, username, extra_usernames, full_name{extra_cols} FROM {tbl} WHERE extra_usernames != ''"
            ).fetchall()
            for r in rows:
                ex_list = [u.lower() for u in _parse_extra_usernames(r["extra_usernames"])]
                if any(u in cand_set for u in ex_list):
                    fb_txt = f"{r['proof'] or ''}\n{r['reason'] or ''}\n{r['proof_url'] or ''}" if tbl == "scammers" else ""
                    _collect(r["user_id"], r["username"], r["extra_usernames"], r["full_name"], fallback_text=fb_txt)

    with db_connect(write=False) as conn:
        if best_uid:
            _scan_table_by_uid(conn, best_uid)
        if search_unames:
            _scan_table_by_unames(conn, search_unames)
        if best_uid and not uid:
            _scan_table_by_uid(conn, best_uid)
        elif best_uid and primary_candidates:
            extra_unames = _merge_username_aliases("", primary_candidates)
            missing_unames = [u for u in extra_unames if u not in search_unames]
            if missing_unames:
                _scan_table_by_unames(conn, missing_unames)

    best_uname = primary_candidates[0] if primary_candidates else uname_clean
    merged_extras = _merge_username_aliases(best_uname, alias_sources, extra_usernames or [])

    best_name = ""
    for nm in name_candidates:
        if not _is_placeholder_name(nm, best_uname, best_uid):
            best_name = nm
            break
    if not best_name and name_candidates:
        best_name = name_candidates[0]

    return {
        "found": found,
        "user_id": best_uid,
        "username": best_uname,
        "extra_usernames": merged_extras,
        "full_name": best_name,
    }


def extract_valid_url(text: Optional[str]) -> str:
    if not text:
        return ""
    m = re.search(r"https?://\S+", text.strip())
    if m:
        return m.group(0).rstrip(".,);]")
    m2 = re.search(r"(?:^|\s)(t\.me/\S+)", text.strip(), re.IGNORECASE)
    if m2:
        return "https://" + m2.group(1).rstrip(".,);]")
    return ""


def _find_row_by_identity(
    conn: sqlite3.Connection,
    table: str,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    extra_usernames: Optional[List[str]] = None,
) -> Optional[sqlite3.Row]:
    if user_id and int(user_id) > 0:
        row = conn.execute(f"SELECT * FROM {table} WHERE user_id=?", (int(user_id),)).fetchone()
        if row:
            return row

    cand_unames = _merge_username_aliases("", [username] if username else [], extra_usernames or [])
    for un in cand_unames:
        row = conn.execute(f"SELECT * FROM {table} WHERE LOWER(username)=?", (un,)).fetchone()
        if row:
            return row

    if cand_unames:
        cand_set = set(cand_unames)
        extra_rows = conn.execute(f"SELECT * FROM {table} WHERE extra_usernames != ''").fetchall()
        for r in extra_rows:
            ex_list = [u.lower() for u in _parse_extra_usernames(r["extra_usernames"])]
            if any(u in cand_set for u in ex_list):
                return r
    return None


def db_add_or_update_scammer(
    user_id: Optional[int],
    username: str,
    full_name: str,
    reason: str,
    proof: str,
    damage: str,
    added_by: int,
    extra_usernames: Optional[List[str]] = None,
    proof_url: str = "",
    proof_media_json: str = "",
    preserve_added_at: bool = False,
) -> int:
    uname_clean = (username or "").strip().lstrip("@").lower()
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    with db_connect(write=True) as conn:
        if user_id:
            conn.execute("DELETE FROM guarantors WHERE user_id=?", (int(user_id),))
        if uname_clean:
            conn.execute("DELETE FROM guarantors WHERE LOWER(username)=?", (uname_clean,))

        existing_by_id = None
        if user_id and int(user_id) > 0:
            existing_by_id = conn.execute("SELECT * FROM scammers WHERE user_id=?", (int(user_id),)).fetchone()

        existing_by_un = _find_row_by_identity(conn, "scammers", user_id=None, username=uname_clean, extra_usernames=extra_usernames)

        existing = existing_by_id or existing_by_un
        dup_unlinked = None
        if existing_by_id and existing_by_un and existing_by_id["id"] != existing_by_un["id"]:
            if existing_by_un["user_id"] is None:
                dup_unlinked = existing_by_un

        if existing:
            old_uname = (existing["username"] or "").strip().lstrip("@").lower()
            target_uname = uname_clean or old_uname
            alias_sources: List[Any] = [existing["extra_usernames"] or "", extra_usernames or []]
            if old_uname and target_uname and old_uname != target_uname:
                alias_sources.insert(0, old_uname)
            if dup_unlinked:
                if dup_unlinked["username"]:
                    alias_sources.append(dup_unlinked["username"])
                if dup_unlinked["extra_usernames"]:
                    alias_sources.append(dup_unlinked["extra_usernames"])
            final_extra = _serialize_extra_usernames(_merge_username_aliases(target_uname, *alias_sources))

            final_proof_url = proof_url or existing["proof_url"] or (dup_unlinked["proof_url"] if dup_unlinked else "") or ""
            final_media_json = proof_media_json if proof_media_json and proof_media_json != "[]" else (existing["proof_media_json"] or "[]")
            final_added_at = existing["added_at"] if preserve_added_at and existing["added_at"] else now_str

            safe_uid = int(user_id) if user_id and not existing["user_id"] else existing["user_id"]
            if dup_unlinked:
                conn.execute("DELETE FROM scammers WHERE id=?", (dup_unlinked["id"],))

            conn.execute(
                """
                UPDATE scammers
                SET user_id = COALESCE(?, user_id),
                    username = CASE WHEN ? != '' THEN ? ELSE username END,
                    extra_usernames = ?,
                    full_name = CASE WHEN ? != '' THEN ? ELSE full_name END,
                    reason = ?,
                    proof = ?,
                    proof_url = ?,
                    proof_media_json = ?,
                    damage = ?,
                    added_by = ?,
                    added_at = ?
                WHERE id = ?
                """,
                (
                    safe_uid,
                    target_uname,
                    target_uname,
                    final_extra,
                    full_name,
                    full_name,
                    reason,
                    proof,
                    final_proof_url,
                    final_media_json,
                    damage,
                    added_by,
                    final_added_at,
                    existing["id"],
                ),
            )
            conn.commit()
            return int(existing["id"])
        else:
            extra_str = _serialize_extra_usernames(_merge_username_aliases(uname_clean, extra_usernames or []))
            cur = conn.execute(
                """
                INSERT INTO scammers (
                    user_id, username, extra_usernames, full_name, reason,
                    proof, proof_url, proof_media_json, damage, added_by, added_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(user_id) if user_id else None,
                    uname_clean,
                    extra_str,
                    full_name,
                    reason,
                    proof,
                    proof_url,
                    proof_media_json or "[]",
                    damage,
                    added_by,
                    now_str,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)


def db_find_scammer(
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    extra_usernames: Optional[List[str]] = None,
) -> Optional[sqlite3.Row]:
    uname_clean = (username or "").strip().lstrip("@").lower()
    with db_connect(write=False) as conn:
        row = _find_row_by_identity(conn, "scammers", user_id=user_id, username=uname_clean, extra_usernames=extra_usernames)
        if row:
            return row

        # Кросс-связка через users_cache / scam_reports, если передан только ID или только username
        if user_id and int(user_id) > 0:
            uc = conn.execute("SELECT username, extra_usernames FROM users_cache WHERE user_id=?", (int(user_id),)).fetchone()
            if uc:
                c_unames = _merge_username_aliases("", uc["username"], uc["extra_usernames"])
                if c_unames:
                    row = _find_row_by_identity(conn, "scammers", user_id=None, username=c_unames[0], extra_usernames=c_unames[1:])
                    if row:
                        return row
        elif uname_clean:
            uc = conn.execute("SELECT user_id FROM users_cache WHERE LOWER(username)=?", (uname_clean,)).fetchone()
            if not uc:
                for cand in conn.execute("SELECT user_id, extra_usernames FROM users_cache WHERE extra_usernames != ''").fetchall():
                    if uname_clean in [u.lower() for u in _parse_extra_usernames(cand["extra_usernames"])]:
                        uc = cand
                        break
            if uc and uc["user_id"]:
                row = _find_row_by_identity(conn, "scammers", user_id=int(uc["user_id"]))
                if row:
                    return row
    return None


def db_get_scammer_by_id(record_id: int) -> Optional[sqlite3.Row]:
    with db_connect(write=False) as conn:
        return conn.execute("SELECT * FROM scammers WHERE id=?", (int(record_id),)).fetchone()


def db_delete_scammer(record_id: int) -> bool:
    with db_connect(write=True) as conn:
        cur = conn.execute("DELETE FROM scammers WHERE id=?", (int(record_id),))
        conn.commit()
        return cur.rowcount > 0


def db_get_scammers_page(page: int = 1, page_size: int = 6) -> Tuple[List[sqlite3.Row], int, int]:
    with db_connect(write=False) as conn:
        total = int(conn.execute("SELECT COUNT(*) AS cnt FROM scammers").fetchone()["cnt"])
        total_pages = max(1, math.ceil(total / page_size))
        page = max(1, min(page, total_pages))
        offset = (page - 1) * page_size
        rows = conn.execute(
            "SELECT * FROM scammers ORDER BY id DESC LIMIT ? OFFSET ?",
            (page_size, offset),
        ).fetchall()
        return rows, total_pages, total


def db_add_or_update_guarantor(
    user_id: Optional[int],
    username: str,
    full_name: str,
    note: str,
    added_by: int,
    extra_usernames: Optional[List[str]] = None,
    preserve_added_at: bool = False,
) -> int:
    uname_clean = (username or "").strip().lstrip("@").lower()
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    with db_connect(write=True) as conn:
        if user_id:
            conn.execute("DELETE FROM scammers WHERE user_id=?", (int(user_id),))
        if uname_clean:
            conn.execute("DELETE FROM scammers WHERE LOWER(username)=?", (uname_clean,))

        existing_by_id = None
        if user_id and int(user_id) > 0:
            existing_by_id = conn.execute("SELECT * FROM guarantors WHERE user_id=?", (int(user_id),)).fetchone()
        existing_by_un = _find_row_by_identity(conn, "guarantors", user_id=None, username=uname_clean, extra_usernames=extra_usernames)
        existing = existing_by_id or existing_by_un

        dup_unlinked = None
        if existing_by_id and existing_by_un and existing_by_id["id"] != existing_by_un["id"]:
            if existing_by_un["user_id"] is None:
                dup_unlinked = existing_by_un

        if existing:
            old_uname = (existing["username"] or "").strip().lstrip("@").lower()
            target_uname = uname_clean or old_uname
            alias_sources: List[Any] = [existing["extra_usernames"] or "", extra_usernames or []]
            if old_uname and target_uname and old_uname != target_uname:
                alias_sources.insert(0, old_uname)
            if dup_unlinked:
                if dup_unlinked["username"]:
                    alias_sources.append(dup_unlinked["username"])
                if dup_unlinked["extra_usernames"]:
                    alias_sources.append(dup_unlinked["extra_usernames"])
            final_extra = _serialize_extra_usernames(_merge_username_aliases(target_uname, *alias_sources))
            final_added_at = existing["added_at"] if preserve_added_at and existing["added_at"] else now_str

            safe_uid = int(user_id) if user_id and not existing["user_id"] else existing["user_id"]
            if dup_unlinked:
                conn.execute("DELETE FROM guarantors WHERE id=?", (dup_unlinked["id"],))

            conn.execute(
                """
                UPDATE guarantors
                SET user_id = COALESCE(?, user_id),
                    username = CASE WHEN ? != '' THEN ? ELSE username END,
                    extra_usernames = ?,
                    full_name = CASE WHEN ? != '' THEN ? ELSE full_name END,
                    note = ?,
                    added_by = ?,
                    added_at = ?
                WHERE id = ?
                """,
                (
                    safe_uid,
                    target_uname,
                    target_uname,
                    final_extra,
                    full_name,
                    full_name,
                    note,
                    added_by,
                    final_added_at,
                    existing["id"],
                ),
            )
            conn.commit()
            return int(existing["id"])
        else:
            extra_str = _serialize_extra_usernames(_merge_username_aliases(uname_clean, extra_usernames or []))
            cur = conn.execute(
                """
                INSERT INTO guarantors (user_id, username, extra_usernames, full_name, note, proof_url, added_by, added_at)
                VALUES (?, ?, ?, ?, ?, '', ?, ?)
                """,
                (int(user_id) if user_id else None, uname_clean, extra_str, full_name, note, added_by, now_str),
            )
            conn.commit()
            return int(cur.lastrowid)


def db_find_guarantor(
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    extra_usernames: Optional[List[str]] = None,
) -> Optional[sqlite3.Row]:
    uname_clean = (username or "").strip().lstrip("@").lower()
    with db_connect(write=False) as conn:
        row = _find_row_by_identity(conn, "guarantors", user_id=user_id, username=uname_clean, extra_usernames=extra_usernames)
        if row:
            return row

        if user_id and int(user_id) > 0:
            uc = conn.execute("SELECT username, extra_usernames FROM users_cache WHERE user_id=?", (int(user_id),)).fetchone()
            if uc:
                c_unames = _merge_username_aliases("", uc["username"], uc["extra_usernames"])
                if c_unames:
                    row = _find_row_by_identity(conn, "guarantors", user_id=None, username=c_unames[0], extra_usernames=c_unames[1:])
                    if row:
                        return row
        elif uname_clean:
            uc = conn.execute("SELECT user_id FROM users_cache WHERE LOWER(username)=?", (uname_clean,)).fetchone()
            if not uc:
                for cand in conn.execute("SELECT user_id, extra_usernames FROM users_cache WHERE extra_usernames != ''").fetchall():
                    if uname_clean in [u.lower() for u in _parse_extra_usernames(cand["extra_usernames"])]:
                        uc = cand
                        break
            if uc and uc["user_id"]:
                row = _find_row_by_identity(conn, "guarantors", user_id=int(uc["user_id"]))
                if row:
                    return row
    return None


def db_get_guarantor_by_id(record_id: int) -> Optional[sqlite3.Row]:
    with db_connect(write=False) as conn:
        return conn.execute("SELECT * FROM guarantors WHERE id=?", (int(record_id),)).fetchone()


def db_delete_guarantor(record_id: int) -> bool:
    with db_connect(write=True) as conn:
        cur = conn.execute("DELETE FROM guarantors WHERE id=?", (int(record_id),))
        conn.commit()
        return cur.rowcount > 0


def db_get_guarantors_page(page: int = 1, page_size: int = 6) -> Tuple[List[sqlite3.Row], int, int]:
    with db_connect(write=False) as conn:
        total = int(conn.execute("SELECT COUNT(*) AS cnt FROM guarantors").fetchone()["cnt"])
        total_pages = max(1, math.ceil(total / page_size))
        page = max(1, min(page, total_pages))
        offset = (page - 1) * page_size
        rows = conn.execute(
            "SELECT * FROM guarantors ORDER BY id DESC LIMIT ? OFFSET ?",
            (page_size, offset),
        ).fetchall()
        return rows, total_pages, total


def build_target_key(user_id: Optional[int], username: str) -> str:
    if user_id:
        return f"id:{user_id}"
    uname = (username or "").strip().lstrip("@").lower()
    return f"un:{uname[:32]}"


def db_get_votes(target_key: str) -> Tuple[int, int]:
    with db_connect(write=False) as conn:
        likes = int(
            conn.execute(
                "SELECT COUNT(*) FROM user_votes WHERE target_key=? AND vote_type='like'",
                (target_key,),
            ).fetchone()[0]
        )
        dislikes = int(
            conn.execute(
                "SELECT COUNT(*) FROM user_votes WHERE target_key=? AND vote_type='dislike'",
                (target_key,),
            ).fetchone()[0]
        )
    return likes, dislikes


def db_cast_vote_once(target_key: str, voter_id: int, vote_type: str) -> Tuple[bool, int, int]:
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    with db_connect(write=True) as conn:
        existing = conn.execute(
            "SELECT id FROM user_votes WHERE target_key=? AND voter_id=?",
            (target_key, int(voter_id)),
        ).fetchone()
        if existing:
            likes = int(conn.execute("SELECT COUNT(*) FROM user_votes WHERE target_key=? AND vote_type='like'", (target_key,)).fetchone()[0])
            dislikes = int(conn.execute("SELECT COUNT(*) FROM user_votes WHERE target_key=? AND vote_type='dislike'", (target_key,)).fetchone()[0])
            return False, likes, dislikes

        conn.execute(
            "INSERT INTO user_votes (target_key, voter_id, vote_type, voted_at) VALUES (?, ?, ?, ?)",
            (target_key, int(voter_id), vote_type, now_str),
        )
        conn.commit()
        likes = int(conn.execute("SELECT COUNT(*) FROM user_votes WHERE target_key=? AND vote_type='like'", (target_key,)).fetchone()[0])
        dislikes = int(conn.execute("SELECT COUNT(*) FROM user_votes WHERE target_key=? AND vote_type='dislike'", (target_key,)).fetchone()[0])
        return True, likes, dislikes


def db_log_check(checker_id: int, query_text: str, result_type: str) -> None:
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    with db_connect(write=True) as conn:
        conn.execute(
            "INSERT INTO check_logs (checker_id, query_text, is_scammer, result_type, checked_at) VALUES (?, ?, ?, ?, ?)",
            (checker_id, query_text[:120], 1 if result_type == "scammer" else 0, result_type, now_str),
        )
        conn.commit()


def db_record_started_user(user_id: Optional[int], username: str = "", full_name: str = "") -> None:
    if not user_id or int(user_id) <= 0:
        return
    uid = int(user_id)
    uname_clean = (username or "").strip().lstrip("@").lower()
    name_clean = (full_name or "").strip()
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    with db_connect(write=True) as conn:
        existing = conn.execute(
            "SELECT username, full_name FROM bot_started_users WHERE user_id=?",
            (uid,),
        ).fetchone()
        if existing:
            if existing["username"] == uname_clean and existing["full_name"] == name_clean:
                return
            conn.execute(
                "UPDATE bot_started_users SET username=?, full_name=? WHERE user_id=?",
                (uname_clean, name_clean, uid),
            )
        else:
            conn.execute(
                "INSERT INTO bot_started_users (user_id, username, full_name, started_at) VALUES (?, ?, ?, ?)",
                (uid, uname_clean, name_clean, now_str),
            )
        conn.commit()


def db_get_stats() -> dict:
    with db_connect(write=False) as conn:
        total_scammers = int(conn.execute("SELECT COUNT(*) FROM scammers").fetchone()[0])
        total_guarantors = int(conn.execute("SELECT COUNT(*) FROM guarantors").fetchone()[0])
        total_checks = int(conn.execute("SELECT COUNT(*) FROM check_logs").fetchone()[0])
        scammer_hits = int(conn.execute("SELECT COUNT(*) FROM check_logs WHERE is_scammer=1").fetchone()[0])
        total_votes = int(conn.execute("SELECT COUNT(*) FROM user_votes").fetchone()[0])
        pending_reports = int(conn.execute("SELECT COUNT(*) FROM scam_reports WHERE status='pending'").fetchone()[0])
        total_mods = int(conn.execute("SELECT COUNT(*) FROM moderators").fetchone()[0])
        total_agreed = int(conn.execute("SELECT COUNT(*) FROM user_agreements").fetchone()[0])
        total_started = int(conn.execute("SELECT COUNT(*) FROM bot_started_users").fetchone()[0])
    return {
        "total_scammers": total_scammers,
        "total_guarantors": total_guarantors,
        "total_checks": total_checks,
        "scammer_hits": scammer_hits,
        "total_votes": total_votes,
        "pending_reports": pending_reports,
        "total_mods": total_mods,
        "total_agreed": total_agreed,
        "total_started": max(total_started, total_agreed),
    }


_MTPROTO_LOCK = asyncio.Lock()
_MTPROTO_CLIENT: Any = None
_MTPROTO_CREDS: Optional[Tuple[int, str]] = None
_ADMIN_SCAN_TS: Dict[int, float] = {}


def _get_mtproto_credentials() -> Tuple[int, str]:
    api_id = TG_API_ID
    api_hash = TG_API_HASH
    if not api_id or not api_hash:
        try:
            raw_id = db_get_setting("mtproto_api_id", "").strip()
            raw_hash = db_get_setting("mtproto_api_hash", "").strip()
            if raw_id.isdigit() and raw_hash:
                api_id = int(raw_id)
                api_hash = raw_hash
        except Exception:
            pass
    return api_id, api_hash


def db_set_mtproto_credentials(api_id: Optional[int], api_hash: str = "") -> None:
    global _MTPROTO_CLIENT, _MTPROTO_CREDS
    if not api_id or not api_hash:
        db_set_setting("mtproto_api_id", "")
        db_set_setting("mtproto_api_hash", "")
    else:
        db_set_setting("mtproto_api_id", str(int(api_id)))
        db_set_setting("mtproto_api_hash", api_hash.strip())
    _MTPROTO_CLIENT = None
    _MTPROTO_CREDS = None


def _is_mtproto_ready() -> Tuple[bool, str]:
    api_id, api_hash = _get_mtproto_credentials()
    if not api_id or not api_hash:
        return False, "нет API_ID/API_HASH"
    try:
        import telethon  # noqa: F401
        return True, "Telethon подключён"
    except ImportError:
        try:
            import pyrogram  # noqa: F401
            return True, "Pyrogram подключён"
        except ImportError:
            return False, "нужен telethon или pyrogram"


async def resolve_username_via_mtproto(username: str) -> Optional[Tuple[str, Optional[int], str, str]]:
    """
    Глобально определяет ID пользователя по @username через MTProto (даже если он не заходил в бот),
    если заданы TG_API_ID / TG_API_HASH (через окружение или /set_api) и установлен telethon/pyrogram.
    Возвращает ("USER", uid, uname, full_name) | ("CHAT", None, "", "") | None.
    """
    global _MTPROTO_CLIENT, _MTPROTO_CREDS
    uname = (username or "").strip().lstrip("@").lower()
    if not uname:
        return None
    api_id, api_hash = _get_mtproto_credentials()
    if not api_id or not api_hash:
        return None

    async with _MTPROTO_LOCK:
        # 1. Пробуем Telethon
        try:
            from telethon import TelegramClient
            from telethon.sessions import MemorySession
            from telethon.tl.types import Channel, Chat, User

            if _MTPROTO_CLIENT is None or _MTPROTO_CREDS != (api_id, api_hash):
                if _MTPROTO_CLIENT is not None:
                    try:
                        await _MTPROTO_CLIENT.disconnect()
                    except Exception:
                        pass
                client = TelegramClient(MemorySession(), api_id, api_hash)
                await client.start(bot_token=BOT_TOKEN)
                _MTPROTO_CLIENT = client
                _MTPROTO_CREDS = (api_id, api_hash)

            if not _MTPROTO_CLIENT.is_connected():
                await _MTPROTO_CLIENT.connect()

            entity = await _MTPROTO_CLIENT.get_entity(uname)
            if isinstance(entity, (Channel, Chat)):
                return ("CHAT", None, "", "")
            if isinstance(entity, User):
                if getattr(entity, "bot", False):
                    return ("BOT", None, "", "")
                uid = int(entity.id)
                u_un = (getattr(entity, "username", None) or uname).strip().lstrip("@").lower()
                u_name = " ".join(
                    p for p in (getattr(entity, "first_name", None), getattr(entity, "last_name", None)) if p
                ).strip()
                db_upsert_user_cache(user_id=uid, username=u_un, full_name=u_name)
                return ("USER", uid, u_un, u_name)
        except ImportError:
            pass
        except Exception as e:
            logger.debug("MTProto Telethon resolve(@%s): %s", uname, e)

        # 2. Фолбэк на Pyrogram
        try:
            from pyrogram import Client as PyroClient
            from pyrogram.enums import ChatType as PyroChatType

            async with PyroClient(
                "krakaze_mtproto_mem",
                api_id=api_id,
                api_hash=api_hash,
                bot_token=BOT_TOKEN,
                in_memory=True,
                no_updates=True,
            ) as app:
                info = await app.get_chat(uname)
                ctype = getattr(info, "type", None)
                if ctype in (PyroChatType.GROUP, PyroChatType.SUPERGROUP, PyroChatType.CHANNEL):
                    return ("CHAT", None, "", "")
                if getattr(info, "is_bot", False):
                    return ("BOT", None, "", "")
                uid = int(info.id)
                if uid > 0:
                    u_un = (getattr(info, "username", None) or uname).strip().lstrip("@").lower()
                    u_name = " ".join(
                        p for p in (getattr(info, "first_name", None), getattr(info, "last_name", None)) if p
                    ).strip()
                    db_upsert_user_cache(user_id=uid, username=u_un, full_name=u_name)
                    return ("USER", uid, u_un, u_name)
        except ImportError:
            pass
        except Exception as e:
            logger.debug("MTProto Pyrogram resolve(@%s): %s", uname, e)

    return None


async def _cache_chat_admins_if_needed(bot, target_uname: str = "", max_chats: int = 5) -> None:
    """Кэширует администраторов общих групп/каналов через Bot API get_chat_administrators (TTL 10 мин)."""
    proof_ch_id, _, _ = db_get_proof_channel()
    cids: List[int] = []
    if proof_ch_id:
        cids.append(int(proof_ch_id))
    for c in _get_known_chat_ids():
        if c not in cids:
            cids.append(c)

    now = time.time()
    uname_low = (target_uname or "").strip().lstrip("@").lower()
    scanned = 0
    for cid in cids:
        if scanned >= max_chats:
            break
        last_ts = _ADMIN_SCAN_TS.get(cid, 0.0)
        if now - last_ts < 600.0:
            continue
        _ADMIN_SCAN_TS[cid] = now
        scanned += 1
        try:
            admins = await bot.get_chat_administrators(cid)
            for cm in admins:
                u = getattr(cm, "user", None)
                if u and not getattr(u, "is_bot", False):
                    _cache_tg_user_obj(u)
                    if uname_low and (getattr(u, "username", None) or "").strip().lstrip("@").lower() == uname_low:
                        return
        except Exception as e:
            logger.debug("get_chat_administrators(%s): %s", cid, e)


# =====================================================================
# ПРАВА ДОСТУПА, СОГЛАШЕНИЕ, МОДЕРАТОРЫ И КАНАЛ ПРУФОВ
# =====================================================================
def is_full_admin(user_id: Optional[int]) -> bool:
    return bool(user_id and int(user_id) in ADMIN_IDS_SET)


def db_has_accepted_terms(user_id: Optional[int]) -> bool:
    if not user_id:
        return False
    with db_connect(write=False) as conn:
        row = conn.execute(
            "SELECT 1 FROM user_agreements WHERE user_id=?",
            (int(user_id),),
        ).fetchone()
        return row is not None


def db_accept_terms(user_id: int) -> None:
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    with db_connect(write=True) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO user_agreements (user_id, accepted_at) VALUES (?, ?)",
            (int(user_id), now_str),
        )
        conn.commit()


def db_set_setting(key: str, value: str) -> None:
    with db_connect(write=True) as conn:
        conn.execute(
            """
            INSERT INTO bot_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value or ""),
        )
        conn.commit()


def db_get_setting(key: str, default: str = "") -> str:
    with db_connect(write=False) as conn:
        row = conn.execute("SELECT value FROM bot_settings WHERE key=?", (key,)).fetchone()
        return str(row[0]) if row and row[0] is not None else default


def db_set_proof_channel(channel_id: Optional[int], channel_username: str = "", channel_title: str = "") -> None:
    if not channel_id:
        db_set_setting("proof_channel_id", "")
        db_set_setting("proof_channel_username", "")
        db_set_setting("proof_channel_title", "")
        return
    db_set_setting("proof_channel_id", str(int(channel_id)))
    db_set_setting("proof_channel_username", (channel_username or "").strip().lstrip("@"))
    db_set_setting("proof_channel_title", (channel_title or "").strip()[:120])


def db_get_proof_channel() -> Tuple[Optional[int], str, str]:
    raw_id = db_get_setting("proof_channel_id", "").strip()
    uname = db_get_setting("proof_channel_username", "").strip().lstrip("@")
    title = db_get_setting("proof_channel_title", "").strip()
    try:
        cid = int(raw_id) if raw_id else None
    except ValueError:
        cid = None
    return cid, uname, title


_KNOWN_CHAT_IDS_CACHE: Optional[List[int]] = None


def _get_known_chat_ids() -> List[int]:
    global _KNOWN_CHAT_IDS_CACHE
    if _KNOWN_CHAT_IDS_CACHE is not None:
        return list(_KNOWN_CHAT_IDS_CACHE)
    raw = db_get_setting("known_chat_ids", "[]").strip()
    cids: List[int] = []
    try:
        parsed = json.loads(raw or "[]")
        if isinstance(parsed, list):
            for x in parsed:
                try:
                    ix = int(x)
                    if ix != 0 and ix not in cids:
                        cids.append(ix)
                except (TypeError, ValueError):
                    continue
    except Exception:
        cids = []
    _KNOWN_CHAT_IDS_CACHE = cids[:40]
    return list(_KNOWN_CHAT_IDS_CACHE)


def _record_known_chat_id(chat_id: Optional[int], remove: bool = False) -> None:
    global _KNOWN_CHAT_IDS_CACHE
    if not chat_id:
        return
    try:
        cid = int(chat_id)
    except (TypeError, ValueError):
        return
    if cid > 0:
        return
    curr = _get_known_chat_ids()
    if remove:
        if cid not in curr:
            return
        updated = [x for x in curr if x != cid]
    else:
        if curr and curr[0] == cid:
            return
        updated = [cid] + [x for x in curr if x != cid]
        updated = updated[:40]
    _KNOWN_CHAT_IDS_CACHE = updated
    db_set_setting("known_chat_ids", json.dumps(updated))


def parse_public_channel_slug(raw: str) -> str:
    """Извлекает публичный @slug канала из ссылки https://t.me/..., t.me/s/... или @username."""
    s = (raw or "").strip()
    m = re.search(
        r"(?:https?://)?(?:t\.me|telegram\.me)/(?:s/)?([A-Za-z0-9_]{4,})",
        s,
        flags=re.IGNORECASE,
    )
    if m:
        slug = m.group(1)
    else:
        slug = s.lstrip("@").split()[0] if s else ""
    slug = re.sub(r"[^A-Za-z0-9_]", "", slug)
    if slug.lower() in ("joinchat", "s", "c", "addstickers", "bot", "proxy", "socks"):
        return ""
    return slug


def _parse_channel_post_records(chunk_html: str, channel_slug: str, msg_id: int) -> List[Dict[str, Any]]:
    """Извлекает одного или нескольких скамеров и описание доказательств из HTML-блока поста t.me/s/."""
    text_m = re.search(
        r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
        chunk_html,
        flags=re.DOTALL,
    )
    if not text_m:
        return []
    raw_inner = text_m.group(1)

    added_at = datetime.now().strftime("%d.%m.%Y %H:%M")
    time_m = re.search(r'<time[^>]+datetime="([^"]+)"', chunk_html)
    if time_m:
        try:
            iso = time_m.group(1).replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso)
            added_at = dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            pass

    found_ids: List[int] = []
    found_unames: List[str] = []

    def _add_uid(val: int) -> None:
        if 10000 <= val <= 9999999999999 and val not in found_ids:
            found_ids.append(val)

    def _add_uname(val: str) -> None:
        u = (val or "").strip().lstrip("@").lower()
        if (
            u
            and u != channel_slug.lower()
            and re.fullmatch(r"[a-z][a-z0-9_]{3,31}", u)
            and u not in found_unames
        ):
            found_unames.append(u)

    # 1. Извлекаем ссылки <a href="...">
    for href in re.findall(r'href="([^"]+)"', raw_inner):
        href_dec = html.unescape(href)
        m_uid = re.search(r"(?:user_id|chat_id|id)=(\d{5,14})(?:\b|$)", href_dec, flags=re.I)
        if m_uid:
            _add_uid(int(m_uid.group(1)))
            continue
        m_tm_num = re.search(r"https?://(?:t\.me|telegram\.me)/@?(?:id)?(\d{5,14})(?:[/?#]|$)", href_dec, flags=re.I)
        if m_tm_num:
            _add_uid(int(m_tm_num.group(1)))
            continue
        m_tm_un = re.search(r"https?://(?:t\.me|telegram\.me)/([A-Za-z][A-Za-z0-9_]{3,31})(?:[/?#]|$)", href_dec, flags=re.I)
        if m_tm_un:
            _add_uname(m_tm_un.group(1))

    # 2. Чистый текст поста
    text_nl = re.sub(r"<br\s*/?>", "\n", raw_inner, flags=re.I)
    text_plain = html.unescape(re.sub(r"<[^>]+>", "", text_nl)).strip()
    if not text_plain:
        return []

    low_plain = text_plain.lower()
    if low_plain.startswith("channel created") or low_plain.startswith("channel name was changed"):
        return []

    # Токены @... / #id... (в каналах пруфов часто пишут @8389559012 или #id8389559012)
    for tok in re.findall(r"[@#](?:id)?([A-Za-z0-9_]{4,32})", text_plain, flags=re.I):
        if tok.isdigit():
            _add_uid(int(tok))
        elif re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,31}", tok):
            _add_uname(tok)

    # Явные упоминания ID: 123456789
    for uid_str in re.findall(r"(?:tg\s*id|uid|айди|идентификатор|\bid\b|🆔)\s*[:=#-]?\s*(\d{5,14})", text_plain, flags=re.I):
        _add_uid(int(uid_str))

    if not found_ids and not found_unames:
        return []

    # 3. Разбор сути (причины) и ущерба
    reason = ""
    damage = "Подтверждённый скам"
    other_lines: List[str] = []
    for raw_line in text_plain.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        m_r = re.match(r"^(?:суть|причина|нарушение|описание|скам)\s*[:\-]\s*(.+)$", line, flags=re.I)
        if m_r:
            reason = m_r.group(1).strip()
            continue
        m_d = re.match(r"^(?:ущерб|сумма|потеря)\s*[:\-]\s*(.+)$", line, flags=re.I)
        if m_d:
            damage = m_d.group(1).strip()[:80]
            continue
        if not re.match(r"^[❌⛔️🚨]*\s*пользовател", line, flags=re.I):
            other_lines.append(line)

    if not reason:
        if other_lines:
            reason = " ".join(other_lines)
        else:
            reason = f"Скам по базе канала @{channel_slug}"
    reason = clip_text(reason, 260)
    proof_url = f"https://t.me/{channel_slug}/{msg_id}"

    out: List[Dict[str, Any]] = []
    if len(found_ids) == 1:
        primary_un = found_unames[0] if found_unames else ""
        extras = found_unames[1:] if len(found_unames) > 1 else []
        out.append({
            "user_id": found_ids[0],
            "username": primary_un,
            "extra_usernames": extras,
            "full_name": f"@{primary_un}" if primary_un else f"ID {found_ids[0]}",
            "reason": reason,
            "damage": damage,
            "proof_url": proof_url,
            "added_at": added_at,
        })
    elif len(found_ids) > 1:
        for idx, uid in enumerate(found_ids):
            un = found_unames[idx] if idx < len(found_unames) else ""
            out.append({
                "user_id": uid,
                "username": un,
                "extra_usernames": [],
                "full_name": f"@{un}" if un else f"ID {uid}",
                "reason": reason,
                "damage": damage,
                "proof_url": proof_url,
                "added_at": added_at,
            })
    else:
        primary_un = found_unames[0]
        extras = found_unames[1:]
        out.append({
            "user_id": None,
            "username": primary_un,
            "extra_usernames": extras,
            "full_name": f"@{primary_un}",
            "reason": reason,
            "damage": damage,
            "proof_url": proof_url,
            "added_at": added_at,
        })
    return out


def _extract_uid_from_tme_post(proof_url: str, username: str = "", timeout_sec: float = 2.0) -> Optional[int]:
    """Пробует извлечь числовой user_id из публичного поста с пруфом (t.me/<slug>/<msg_id>)."""
    url = (proof_url or "").strip()
    if not url:
        return None
    m = re.match(r"^https?://(?:t\.me|telegram\.me)/([A-Za-z][A-Za-z0-9_]{3,})/(\d+)", url, flags=re.IGNORECASE)
    if not m:
        return None
    slug, msg_id = m.group(1), int(m.group(2))
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
    }
    try:
        resp = requests.get(f"https://t.me/{slug}/{msg_id}?embed=1", headers=headers, timeout=timeout_sec)
        if resp.status_code != 200 or not resp.text:
            return None
        recs = _parse_channel_post_records(resp.text, slug, msg_id)
        if not recs:
            return None
        uname_clean = (username or "").strip().lstrip("@").lower()
        if uname_clean:
            for r in recs:
                r_un = (r.get("username") or "").lower()
                r_ex = [u.lower() for u in (r.get("extra_usernames") or [])]
                if uname_clean == r_un or uname_clean in r_ex:
                    if r.get("user_id"):
                        return int(r["user_id"])
        if len(recs) == 1 and recs[0].get("user_id"):
            return int(recs[0]["user_id"])
    except Exception:
        pass
    return None


def db_bulk_import_scraped_scammers(records: List[Dict[str, Any]], added_by: int = 0) -> Tuple[int, int]:
    """Пакетно добавляет выкачанных из канала скамеров в base.db без создания дублей."""
    if not records:
        return 0, 0
    inserted = 0
    skipped = 0
    default_admin = added_by or (ADMIN_IDS[0] if ADMIN_IDS else 0)

    with db_connect(write=True) as conn:
        existing_ids = set(
            int(r[0]) for r in conn.execute("SELECT user_id FROM scammers WHERE user_id IS NOT NULL").fetchall()
        )
        existing_unames = set()
        for r in conn.execute("SELECT username, extra_usernames FROM scammers").fetchall():
            if r[0]:
                existing_unames.add(str(r[0]).strip().lstrip("@").lower())
            if r[1]:
                for eu in str(r[1]).split(","):
                    eu_c = eu.strip().lstrip("@").lower()
                    if eu_c:
                        existing_unames.add(eu_c)

        to_insert = []
        for rec in records:
            uid = rec.get("user_id")
            uname = (rec.get("username") or "").strip().lstrip("@").lower()
            extras = [u.strip().lstrip("@").lower() for u in rec.get("extra_usernames", []) if u]
            if uid and uid in existing_ids:
                skipped += 1
                continue
            if uname and uname in existing_unames:
                skipped += 1
                continue
            if uid:
                existing_ids.add(uid)
            if uname:
                existing_unames.add(uname)
            for eu in extras:
                existing_unames.add(eu)

            to_insert.append((
                uid,
                uname,
                ",".join(extras),
                rec.get("full_name") or (f"@{uname}" if uname else f"ID {uid}"),
                rec.get("reason") or "Подтверждённый скам",
                rec.get("proof_url") or "",
                rec.get("proof_url") or "",
                "[]",
                rec.get("damage") or "Подтверждённый скам",
                default_admin,
                rec.get("added_at") or datetime.now().strftime("%d.%m.%Y %H:%M"),
            ))

        if to_insert:
            conn.executemany(
                """
                INSERT INTO scammers (
                    user_id, username, extra_usernames, full_name, reason,
                    proof, proof_url, proof_media_json, damage, added_by, added_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                to_insert,
            )
            conn.commit()
            inserted = len(to_insert)

    return inserted, skipped


def scrape_public_channel_sync(
    channel_input: str,
    added_by: int = 0,
    max_pages: int = 400,
    progress_cb=None,
) -> Dict[str, Any]:
    """
    Выкачивает все доступные посты с публичного Telegram-канала (через веб-превью t.me/s/<slug>)
    без необходимости добавления бота в канал, импортирует в base.db и выгружает в Firebase.
    """
    slug = parse_public_channel_slug(channel_input)
    if not slug:
        return {"ok": False, "error": "Не удалось распознать имя канала (укажите @channel или https://t.me/...)."}

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
    })

    seen_msg_ids: set = set()
    all_records: List[Dict[str, Any]] = []
    before_id: Optional[int] = None
    pages_fetched = 0
    posts_parsed = 0

    try:
        for _ in range(max_pages):
            url = f"https://t.me/s/{slug}" + (f"?before={before_id}" if before_id else "")
            resp = session.get(url, timeout=18)
            if resp.status_code != 200:
                if pages_fetched == 0:
                    return {"ok": False, "error": f"Канал @{slug} недоступен или закрыт (HTTP {resp.status_code})."}
                break

            page_html = resp.text
            if pages_fetched == 0 and f'data-post="{slug}/' not in page_html and "tgme_channel_info" not in page_html:
                return {"ok": False, "error": f"Канал @{slug} не найден или у него отключён публичный просмотр."}

            pages_fetched += 1
            parts = page_html.split('data-post="')
            page_ids: List[int] = []
            new_on_page = 0

            for chunk in parts[1:]:
                m_post = re.match(rf"{re.escape(slug)}/(\d+)\"", chunk, flags=re.I)
                if not m_post:
                    continue
                msg_id = int(m_post.group(1))
                page_ids.append(msg_id)
                if msg_id in seen_msg_ids:
                    continue
                seen_msg_ids.add(msg_id)
                new_on_page += 1
                posts_parsed += 1
                recs = _parse_channel_post_records(chunk, slug, msg_id)
                if recs:
                    all_records.extend(recs)

            if progress_cb and (pages_fetched == 1 or pages_fetched % 15 == 0):
                try:
                    progress_cb(pages_fetched, posts_parsed, len(all_records))
                except Exception:
                    pass

            if not page_ids or new_on_page == 0:
                break

            min_id = min(page_ids)
            if before_id is not None and min_id >= before_id:
                break
            if min_id <= 1:
                break
            before_id = min_id
            time.sleep(0.06)
    except Exception as ex:
        if not all_records:
            return {"ok": False, "error": f"Ошибка при выгрузке @{slug}: {str(ex)[:180]}"}
    finally:
        session.close()

    inserted, skipped = db_bulk_import_scraped_scammers(all_records, added_by=added_by)
    if slug.lower() == INITIAL_SEED_CHANNEL.lower() and (inserted > 0 or skipped > 0):
        db_set_setting("initial_loneasproofs_seeded", "1")

    firebase_saved = False
    if inserted > 0 or slug.lower() == INITIAL_SEED_CHANNEL.lower():
        firebase_saved = firebase_manager.upload_db_to_cloud(force=True)

    return {
        "ok": True,
        "channel": slug,
        "pages_fetched": pages_fetched,
        "posts_parsed": posts_parsed,
        "records_extracted": len(all_records),
        "inserted": inserted,
        "skipped": skipped,
        "firebase_saved": firebase_saved,
    }


async def _initial_seed_loneasproofs_task() -> None:
    """На старте при пустой базе скачивает исходную базу из @loneasproofs и сохраняет её в Firebase."""
    try:
        stats = db_get_stats()
        already_seeded = db_get_setting("initial_loneasproofs_seeded", "") == "1"
        if stats["total_scammers"] == 0 and not already_seeded:
            logger.info("[Seed] Начальная база пуста - выкачиваю исходные данные из @%s...", INITIAL_SEED_CHANNEL)
            res = await asyncio.to_thread(
                scrape_public_channel_sync,
                INITIAL_SEED_CHANNEL,
                ADMIN_IDS[0] if ADMIN_IDS else 0,
            )
            if res.get("ok"):
                logger.info(
                    "[Seed] Готово! Канал @%s: постов=%s, добавлено=%s, в Firebase=%s",
                    res["channel"],
                    res["posts_parsed"],
                    res["inserted"],
                    res["firebase_saved"],
                )
            else:
                logger.warning("[Seed] Не удалось выкачать @%s: %s", INITIAL_SEED_CHANNEL, res.get("error"))
    except Exception as e:
        logger.warning("[Seed] Фоновая ошибка инициализации базы из канала: %s", e)


def db_add_moderator(user_id: int, username: str, full_name: str, added_by: int) -> bool:
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    uname_clean = (username or "").strip().lstrip("@").lower()
    with db_connect(write=True) as conn:
        conn.execute(
            """
            INSERT INTO moderators (user_id, username, full_name, added_by, added_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = CASE WHEN excluded.username != '' THEN excluded.username ELSE moderators.username END,
                full_name = CASE WHEN excluded.full_name != '' THEN excluded.full_name ELSE moderators.full_name END,
                added_by = excluded.added_by,
                added_at = excluded.added_at
            """,
            (int(user_id), uname_clean, (full_name or "").strip()[:120], int(added_by), now_str),
        )
        conn.commit()
    return True


def db_remove_moderator(user_id: int) -> bool:
    with db_connect(write=True) as conn:
        cur = conn.execute("DELETE FROM moderators WHERE user_id=?", (int(user_id),))
        conn.commit()
        return cur.rowcount > 0


def db_is_moderator(user_id: Optional[int]) -> bool:
    if not user_id:
        return False
    with db_connect(write=False) as conn:
        row = conn.execute("SELECT 1 FROM moderators WHERE user_id=?", (int(user_id),)).fetchone()
        return row is not None


def db_get_moderators() -> List[sqlite3.Row]:
    with db_connect(write=False) as conn:
        return conn.execute("SELECT * FROM moderators ORDER BY id DESC").fetchall()


def is_reviewer(user_id: Optional[int]) -> bool:
    return bool(user_id and (is_full_admin(user_id) or db_is_moderator(user_id)))


def get_all_reviewer_ids() -> List[int]:
    result: List[int] = []
    seen = set()
    for uid in ADMIN_IDS:
        if uid not in seen:
            seen.add(uid)
            result.append(uid)
    for row in db_get_moderators():
        uid = int(row["user_id"])
        if uid not in seen:
            seen.add(uid)
            result.append(uid)
    return result


# =====================================================================
# БАЗА ДАННЫХ: ЖАЛОБЫ НА СКАМЕРОВ И РОТАЦИЯ ПО АДМИНАМ
# =====================================================================
def db_create_scam_report(
    reporter_id: int,
    reporter_username: str,
    reporter_name: str,
    target_id: Optional[int],
    target_username: str,
    target_name: str,
    description: str,
    media_items: List[Dict[str, str]],
) -> int:
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    with db_connect(write=True) as conn:
        cur = conn.execute(
            """
            INSERT INTO scam_reports (
                reporter_id, reporter_username, reporter_name,
                target_id, target_username, target_name,
                description, media_json, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                int(reporter_id),
                (reporter_username or "").lstrip("@"),
                reporter_name or "",
                int(target_id) if target_id else None,
                (target_username or "").lstrip("@").lower(),
                target_name or "",
                description,
                json.dumps(media_items, ensure_ascii=False),
                now_str,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def db_get_scam_report(report_id: int) -> Optional[sqlite3.Row]:
    with db_connect(write=False) as conn:
        return conn.execute("SELECT * FROM scam_reports WHERE id=?", (int(report_id),)).fetchone()


def db_get_pending_reports() -> List[sqlite3.Row]:
    with db_connect(write=False) as conn:
        return conn.execute("SELECT * FROM scam_reports WHERE status='pending' ORDER BY id ASC").fetchall()


def db_update_report_assignment(report_id: int, admin_id: int, msg_ids: List[int]) -> None:
    with db_connect(write=True) as conn:
        conn.execute(
            """
            UPDATE scam_reports
            SET assigned_admin_id = ?,
                assigned_at = ?,
                admin_msg_ids_json = ?
            WHERE id = ?
            """,
            (int(admin_id), time.time(), json.dumps(msg_ids), int(report_id)),
        )
        conn.commit()


def db_finalize_report(report_id: int, status: str, admin_id: int, reject_reason: str = "") -> None:
    with db_connect(write=True) as conn:
        conn.execute(
            """
            UPDATE scam_reports
            SET status = ?,
                decision_by = ?,
                reject_reason = ?,
                admin_msg_ids_json = '[]'
            WHERE id = ?
            """,
            (status, int(admin_id), reject_reason, int(report_id)),
        )
        conn.commit()


# =====================================================================
# СТРОГАЯ ВАЛИДАЦИЯ ПОЛЬЗОВАТЕЛЕЙ (ОТКЛОНЕНИЕ ГРУПП, КАНАЛОВ И ФЕЙКОВ)
# =====================================================================
def parse_user_query(raw_text: str) -> Tuple[Optional[int], str]:
    text = (raw_text or "").strip()
    if not text:
        return None, ""

    found_id: Optional[int] = None
    found_uname: str = ""

    m_tg_id = re.search(
        r"tg://[A-Za-z0-9_]+\?(?:[^#\s]*&)?(?:user_id|chat_id|id)=(\d{5,20})",
        text,
        re.IGNORECASE,
    )
    if m_tg_id:
        found_id = int(m_tg_id.group(1))

    m_tg_dom = re.search(
        r"tg://resolve\?(?:[^#\s]*&)?domain=([A-Za-z][A-Za-z0-9_]{2,34})",
        text,
        re.IGNORECASE,
    )
    if m_tg_dom:
        found_uname = m_tg_dom.group(1).lower()

    if not found_id:
        m_web_id = re.search(r"https?://web\.telegram\.org/[a-z]/#(\d{5,20})(?:[/?&\s]|$)", text, re.IGNORECASE)
        if m_web_id:
            found_id = int(m_web_id.group(1))

    if not found_uname:
        m_web_un = re.search(r"https?://web\.telegram\.org/[a-z]/#@?([A-Za-z][A-Za-z0-9_]{2,34})(?:[/?&\s]|$)", text, re.IGNORECASE)
        if m_web_un:
            found_uname = m_web_un.group(1).lower()

    if not found_id:
        m_tme_id = re.search(r"(?:https?://)?(?:t\.me|telegram\.me)/@?(?:id)?(\d{5,20})(?:[/?#\s]|$)", text, re.IGNORECASE)
        if m_tme_id:
            found_id = int(m_tme_id.group(1))

    if not found_id:
        m_pref_id = re.search(
            r"(?:^|\b|[\s(>])(?:tg\s*id|uid|айди|идентификатор|id|🆔)\s*[:=#-]?\s*(\d{5,20})\b",
            text,
            re.IGNORECASE,
        )
        if m_pref_id:
            found_id = int(m_pref_id.group(1))

    if not found_id:
        m_at_num = re.search(r"(?:^|\s)[@#](?:id)?(\d{5,20})(?:\b|$)", text, re.IGNORECASE)
        if m_at_num:
            found_id = int(m_at_num.group(1))

    # Ссылки вида t.me/s/channel -> извлекаем сам юзернейм для последующей проверки
    if not found_uname:
        m_tme_s = re.search(r"(?:https?://)?(?:t\.me|telegram\.me)/s/([A-Za-z][A-Za-z0-9_]{2,34})", text, re.IGNORECASE)
        if m_tme_s:
            found_uname = m_tme_s.group(1).lower()

    if not found_uname:
        m_link = re.search(r"(?:https?://)?(?:t\.me|telegram\.me)/@?([A-Za-z][A-Za-z0-9_]{2,34})", text, re.IGNORECASE)
        if m_link:
            cand = m_link.group(1).lower()
            if cand not in ("joinchat", "addlist", "addstickers", "addemoji", "share", "iv", "proxy", "socks", "s", "c", "boost", "nft"):
                found_uname = cand

    first_token = text.split()[0].strip().lstrip("#")
    if not found_id and first_token.lstrip("@").isdigit() and 5 <= len(first_token.lstrip("@")) <= 20:
        found_id = int(first_token.lstrip("@"))

    if not found_uname:
        m_at_uname = re.search(r"@([A-Za-z][A-Za-z0-9_]{2,34})", text)
        if m_at_uname:
            found_uname = m_at_uname.group(1).lower()

    if not found_uname and not found_id:
        uname_candidate = first_token.lstrip("@")
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{2,34}", uname_candidate):
            found_uname = uname_candidate.lower()

    if not found_id:
        m_any_num = re.search(r"(?:^|\s)(\d{5,15})(?:\s|$)", text)
        if m_any_num:
            found_id = int(m_any_num.group(1))

    return found_id, found_uname


def _cache_tg_user_obj(u) -> None:
    if not u or getattr(u, "is_bot", False):
        return
    uid = getattr(u, "id", None)
    if not uid or int(uid) <= 0:
        return
    uname = (getattr(u, "username", None) or "").strip().lstrip("@").lower()
    fname = " ".join(p for p in (getattr(u, "first_name", None), getattr(u, "last_name", None)) if p).strip()
    db_upsert_user_cache(user_id=int(uid), username=uname, full_name=fname)


def extract_target_from_message(
    message,
    override_text: Optional[str] = None,
) -> Tuple[Optional[int], str, str, Optional[str]]:
    """
    Извлекает (user_id, username, full_name, rejection_error).
    Поддерживает users_shared / user_shared (кнопка «Выбрать пользователя»),
    пересылку сообщений, контакты, text_mention, ссылки и @username/ID.
    Отклоняет каналы, группы, инвайт-ссылки и ботов.
    """
    if getattr(message, "reply_to_message", None) and getattr(message.reply_to_message, "from_user", None):
        _cache_tg_user_obj(message.reply_to_message.from_user)

    if override_text is None:
        users_shared = getattr(message, "users_shared", None)
        if users_shared:
            shared_list = list(getattr(users_shared, "users", None) or [])
            if shared_list:
                su = shared_list[0]
                su_id = getattr(su, "user_id", None)
                if su_id:
                    su_uname = (getattr(su, "username", None) or "").strip().lstrip("@").lower()
                    su_name = " ".join(
                        p for p in (getattr(su, "first_name", None), getattr(su, "last_name", None)) if p
                    ).strip()
                    db_upsert_user_cache(user_id=int(su_id), username=su_uname, full_name=su_name)
                    return int(su_id), su_uname, su_name, None

        user_shared = getattr(message, "user_shared", None)
        if user_shared and getattr(user_shared, "user_id", None):
            su_id = int(user_shared.user_id)
            db_upsert_user_cache(user_id=su_id)
            return su_id, "", "", None

        fwd_origin = getattr(message, "forward_origin", None)
        origin_type = getattr(fwd_origin, "type", "") if fwd_origin else ""
        if origin_type in ("channel", "chat"):
            return None, "", "", "Группы и каналы не проверяются! Укажите личный аккаунт пользователя."

        if getattr(message, "forward_from_chat", None):
            return None, "", "", "Группы и каналы не проверяются! Укажите личный аккаунт пользователя."

        fwd_from = getattr(message, "forward_from", None)
        if not fwd_from and fwd_origin:
            fwd_from = getattr(fwd_origin, "sender_user", None)

        if fwd_from:
            if getattr(fwd_from, "is_bot", False):
                return None, "", "", "Боты не проверяются! Укажите аккаунт реального пользователя."
            fwd_name = " ".join(p for p in (fwd_from.first_name, fwd_from.last_name) if p).strip()
            db_upsert_user_cache(
                user_id=fwd_from.id,
                username=fwd_from.username or "",
                full_name=fwd_name,
            )
            return fwd_from.id, (fwd_from.username or "").lower(), fwd_name, None

        # Поддержка пересланного/отправленного контакта Telegram
        contact = getattr(message, "contact", None)
        if contact and getattr(contact, "user_id", None):
            c_name = " ".join(p for p in (contact.first_name, contact.last_name) if p).strip()
            db_upsert_user_cache(user_id=contact.user_id, full_name=c_name)
            return int(contact.user_id), "", c_name, None
    else:
        fwd_origin = None
        origin_type = ""

    entities = getattr(message, "entities", None) or getattr(message, "caption_entities", None) or []
    for ent in entities:
        ent_type = getattr(ent, "type", None)
        if ent_type == "text_mention" and getattr(ent, "user", None):
            u = ent.user
            if getattr(u, "is_bot", False):
                return None, "", "", "Боты не проверяются! Укажите аккаунт реального пользователя."
            u_name = " ".join(p for p in (u.first_name, u.last_name) if p).strip()
            db_upsert_user_cache(user_id=u.id, username=u.username or "", full_name=u_name)
            return u.id, (u.username or "").lower(), u_name, None
        if ent_type == "text_link" and getattr(ent, "url", None):
            url_str = str(ent.url)
            if re.search(r"tg://[A-Za-z0-9_]+\?(?:[^#\s]*&)?(?:user_id|chat_id|id)=-\d+", url_str, re.IGNORECASE):
                return None, "", "", "Группы и каналы не проверяются! Укажите личный ID пользователя."
            l_id, l_un = parse_user_query(url_str)
            if l_id or l_un:
                return l_id, l_un, "", None

    if override_text is not None:
        raw_text = override_text.strip()
    else:
        raw_text = (message.text or message.caption or "").strip()
        if raw_text.lower().startswith("/check"):
            parts = raw_text.split(maxsplit=1)
            raw_text = parts[1].strip() if len(parts) > 1 else ""

    if re.search(r"t\.me/(?:\+|joinchat/|c/\d+)", raw_text, re.IGNORECASE):
        return None, "", "", "Ссылки на группы и каналы не проверяются! Укажите личный аккаунт пользователя."

    if re.search(r"tg://[A-Za-z0-9_]+\?(?:[^#\s]*&)?(?:user_id|chat_id|id)=-\d+", raw_text, re.IGNORECASE):
        return None, "", "", "Группы и каналы не проверяются! Укажите личный ID пользователя."

    if re.search(r"web\.telegram\.org/[a-z]/#-\d+", raw_text, re.IGNORECASE):
        return None, "", "", "Группы и каналы не проверяются! Укажите личный аккаунт пользователя."

    first_tok = raw_text.split()[0] if raw_text else ""
    if re.match(r"^-100\d+$", first_tok) or (first_tok.startswith("-") and first_tok[1:].isdigit()):
        return None, "", "", "Группы и каналы не проверяются! Укажите личный ID пользователя."

    q_id, q_uname = parse_user_query(raw_text)
    if not q_id and not q_uname and origin_type == "hidden_user":
        sender_hidden_name = (getattr(fwd_origin, "sender_user_name", "") or "").strip()
        who = f" («{sender_hidden_name}»)" if sender_hidden_name else ""
        return (
            None,
            "",
            "",
            f"Пользователь{who} скрыл свой профиль при пересылке сообщений. Отправьте его @username или числовой Telegram ID.",
        )
    return q_id, q_uname, "", None


def _extract_reply_target_user(reply_msg) -> Tuple[Optional[int], str, str, Optional[str]]:
    """Извлекает проверяемого пользователя из сообщения, на которое ответили командой «проверить» / «чек»."""
    if not reply_msg:
        return None, "", "", None
    r_user = getattr(reply_msg, "from_user", None)
    if r_user:
        if getattr(r_user, "is_bot", False):
            # Если ответили на пересланное ботом сообщение - пробуем достать автора оригинала
            fwd_u = getattr(reply_msg, "forward_from", None)
            if not fwd_u and getattr(reply_msg, "forward_origin", None):
                fwd_u = getattr(reply_msg.forward_origin, "sender_user", None)
            if fwd_u and not getattr(fwd_u, "is_bot", False):
                fname = " ".join(p for p in (fwd_u.first_name, fwd_u.last_name) if p).strip()
                _cache_tg_user_obj(fwd_u)
                return int(fwd_u.id), (fwd_u.username or "").lower(), fname, None
            return None, "", "", "Боты не проверяются! Укажите аккаунт реального пользователя."
        fname = " ".join(p for p in (r_user.first_name, r_user.last_name) if p).strip()
        _cache_tg_user_obj(r_user)
        return int(r_user.id), (r_user.username or "").lower(), fname, None

    if getattr(reply_msg, "sender_chat", None) or getattr(reply_msg, "forward_from_chat", None):
        return None, "", "", "Группы и каналы не проверяются! Укажите личный аккаунт пользователя."
    return extract_target_from_message(reply_msg)


def _extract_group_check_command(msg_obj) -> Tuple[bool, Optional[int], str, str, str, Optional[str]]:
    """
    Распознаёт групповые команды:
    - «проверить @username» / «чек 123456» / «проверить https://t.me/...»
    - ответ (reply) на сообщение пользователя словами «проверить» / «чек»
    """
    raw_text = (getattr(msg_obj, "text", None) or getattr(msg_obj, "caption", None) or "").strip()
    if not raw_text:
        return False, None, "", "", "", None

    bot_slug = re.escape(BOT_USERNAME.lstrip("@"))
    m_cmd = re.match(
        rf"^(?:[/!])?(?:проверить|чек|check)(?:@{bot_slug})?(?:\s+([\s\S]+))?$",
        raw_text,
        flags=re.IGNORECASE,
    )
    if not m_cmd:
        return False, None, "", "", "", None

    arg_part = (m_cmd.group(1) or "").strip()
    if arg_part:
        q_id, q_uname, fwd_name, val_err = extract_target_from_message(msg_obj, override_text=arg_part)
        return True, q_id, q_uname, fwd_name, arg_part, val_err

    reply_msg = getattr(msg_obj, "reply_to_message", None)
    if reply_msg:
        q_id, q_uname, fwd_name, val_err = _extract_reply_target_user(reply_msg)
        return True, q_id, q_uname, fwd_name, str(q_id or q_uname or "reply"), val_err

    return True, None, "", "", "", "__EMPTY_GROUP_CHECK__"


def _inspect_public_tme_page(
    username: str,
    fetch_avatar: bool = True,
    timeout_sec: float = 6.0,
) -> Tuple[str, str, Optional[bytes]]:
    """
    Проверяет публичную страницу t.me/<username>:
    - entity_kind: 'user' | 'group_or_channel' | 'not_found' | 'unknown'
    """
    uname = (username or "").strip().lstrip("@")
    if not uname:
        return "not_found", "", None

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
    }
    try:
        resp = requests.get(f"https://t.me/{uname}", headers=headers, timeout=timeout_sec)
        if resp.status_code == 404:
            return "not_found", "", None
        if resp.status_code != 200:
            return "unknown", "", None
        page = resp.text

        if re.search(r'class="tgme_page_extra"[^>]*>[^<]*(?:subscribers|members|подписчик|участник)', page, re.IGNORECASE):
            return "group_or_channel", "", None
        if 'class="tgme_page_context_link"' in page or "tgme_channel_info" in page:
            return "group_or_channel", "", None

        m_title = re.search(r'<div[^>]+class="tgme_page_title"[^>]*>(.*?)</div>', page, re.DOTALL | re.IGNORECASE)
        if not m_title:
            return "not_found", "", None

        raw_title = re.sub(r"<[^>]+>", "", m_title.group(1))
        disp_name = html.unescape(raw_title).strip()
        if not disp_name:
            return "not_found", "", None

        avatar_bytes: Optional[bytes] = None
        if fetch_avatar:
            m_img = re.search(
                r'<img[^>]+class="[^"]*tgme_page_photo_image[^"]*"[^>]+src="([^"]+)"',
                page,
                re.IGNORECASE,
            )
            if not m_img:
                m_img = re.search(
                    r'<img[^>]+src="([^"]+)"[^>]+class="[^"]*tgme_page_photo_image[^"]*"',
                    page,
                    re.IGNORECASE,
                )
            if m_img:
                img_url = html.unescape(m_img.group(1)).strip()
                if img_url.startswith("http") and "t_logo" not in img_url:
                    img_resp = requests.get(img_url, headers=headers, timeout=timeout_sec)
                    if img_resp.status_code == 200 and len(img_resp.content) > 256:
                        avatar_bytes = img_resp.content

        return "user", disp_name, avatar_bytes
    except Exception as e:
        logger.debug("Ошибка проверки t.me/%s: %s", uname, e)
        return "unknown", "", None


def _save_avatar_cache(avatar_bytes: bytes, user_id: Optional[int], username: str) -> None:
    if not avatar_bytes:
        return
    if user_id:
        try:
            (AVATARS_CACHE_DIR / f"av_{int(user_id)}.jpg").write_bytes(avatar_bytes)
        except Exception:
            pass
    uname_clean = (username or "").strip().lstrip("@").lower()
    if uname_clean:
        try:
            (AVATARS_CACHE_DIR / f"av_un_{uname_clean}.jpg").write_bytes(avatar_bytes)
        except Exception:
            pass


def _load_avatar_cache(user_id: Optional[int], username: str) -> Optional[bytes]:
    if user_id:
        p = AVATARS_CACHE_DIR / f"av_{int(user_id)}.jpg"
        if p.exists():
            try:
                return p.read_bytes()
            except Exception:
                pass
    uname_clean = (username or "").strip().lstrip("@").lower()
    if uname_clean:
        p2 = AVATARS_CACHE_DIR / f"av_un_{uname_clean}.jpg"
        if p2.exists():
            try:
                return p2.read_bytes()
            except Exception:
                pass
    return None


async def validate_and_resolve_user(
    bot,
    user_id: Optional[int],
    username: str,
    fetch_avatar: bool = True,
) -> Tuple[bool, str, Optional[int], str, List[str], str, Optional[bytes]]:
    if user_id is not None and int(user_id) <= 0:
        return False, "Группы и каналы не проверяются! Укажите личный аккаунт пользователя.", None, "", [], "", None

    resolved_id: Optional[int] = int(user_id) if user_id else None
    resolved_uname = (username or "").strip().lstrip("@").lower()
    extra_usernames: List[str] = []
    resolved_name = ""
    avatar_bytes: Optional[bytes] = None
    verified_exists = False
    in_local_records = False

    # 1. Кросс-поиск по всей локальной базе (users_cache, scammers, guarantors, moderators, scam_reports)
    known = db_lookup_known_identity(user_id=resolved_id, username=resolved_uname)
    in_scam = db_find_scammer(user_id=resolved_id, username=resolved_uname)
    in_guar = db_find_guarantor(user_id=resolved_id, username=resolved_uname)

    if known["found"] or in_scam or in_guar:
        in_local_records = True
        verified_exists = True
    if known["user_id"] and not resolved_id:
        resolved_id = int(known["user_id"])
    if known["username"] and not resolved_uname:
        resolved_uname = known["username"]
    if known["extra_usernames"]:
        extra_usernames = _merge_username_aliases(resolved_uname, extra_usernames, known["extra_usernames"])
    if known["full_name"] and not resolved_name:
        resolved_name = known["full_name"]

    # Валидный числовой Telegram ID (от 5 цифр) всегда разрешается для проверки по ID
    if resolved_id and 10000 <= int(resolved_id) <= 9999999999999:
        verified_exists = True

    # 2. Живой запрос к Telegram Bot API (по ID и по @username)
    targets: List[Any] = []
    if resolved_id:
        targets.append(resolved_id)
    if resolved_uname:
        targets.append(f"@{resolved_uname}")
    for alias in extra_usernames[:2]:
        if alias and f"@{alias}" not in targets:
            targets.append(f"@{alias}")

    got_private_chat = False
    for chat_target in targets:
        try:
            chat = await bot.get_chat(chat_target)
            if chat:
                if chat.type != ChatType.PRIVATE:
                    return (
                        False,
                        "Группы и каналы не проверяются! Укажите личный аккаунт пользователя.",
                        None,
                        "",
                        [],
                        "",
                        None,
                    )

                got_private_chat = True
                verified_exists = True
                prev_uname = resolved_uname
                resolved_id = int(chat.id)

                live_uname = (chat.username or "").strip().lstrip("@").lower()
                active_list = [u.strip().lstrip("@").lower() for u in (getattr(chat, "active_usernames", None) or []) if u]
                if live_uname:
                    resolved_uname = live_uname
                elif active_list and not resolved_uname:
                    resolved_uname = active_list[0]

                # Сохраняем прежний юзернейм в истории, если пользователь его сменил
                alias_pool: List[Any] = [extra_usernames, active_list]
                if prev_uname and resolved_uname and prev_uname != resolved_uname:
                    alias_pool.append(prev_uname)
                extra_usernames = _merge_username_aliases(resolved_uname, *alias_pool)

                name_parts = [p for p in (chat.first_name, chat.last_name) if p]
                api_name = " ".join(name_parts).strip() or (chat.title or "")
                if api_name:
                    resolved_name = api_name

                if fetch_avatar and chat.photo:
                    fid = chat.photo.big_file_id or chat.photo.small_file_id
                    if fid:
                        tg_file = await bot.get_file(fid)
                        bio = io.BytesIO()
                        await tg_file.download_to_memory(bio)
                        avatar_bytes = bio.getvalue()
                break
        except BadRequest as e:
            err = str(e).lower()
            if "chat not found" in err or "username not occupied" in err or "user not found" in err:
                continue
        except Exception as e:
            logger.debug("get_chat(%s): %s", chat_target, e)

    # Если get_chat("@username") только что раскрыл user_id, подтягиваем историю этого ID из базы
    if resolved_id and not in_local_records:
        known_by_id = db_lookup_known_identity(user_id=resolved_id, username=resolved_uname)
        if known_by_id["found"]:
            extra_usernames = _merge_username_aliases(
                resolved_uname or known_by_id["username"],
                extra_usernames,
                known_by_id["username"],
                known_by_id["extra_usernames"],
            )
            if not resolved_uname and known_by_id["username"]:
                resolved_uname = known_by_id["username"]
            if not resolved_name and known_by_id["full_name"]:
                resolved_name = known_by_id["full_name"]

    # 2.5 Если в базе скамера есть публичный proof_url, а ID ещё не прописан - пробуем достать его из поста пруфов
    if not resolved_id and in_scam and in_scam["proof_url"]:
        post_uid = await asyncio.to_thread(
            _extract_uid_from_tme_post,
            str(in_scam["proof_url"]),
            resolved_uname,
            1.8 if fetch_avatar else 1.2,
        )
        if post_uid:
            resolved_id = int(post_uid)
            verified_exists = True

    # 2.7 Глобальное определение ID через MTProto (если заданы API_ID/API_HASH и telethon/pyrogram)
    if not resolved_id and resolved_uname:
        try:
            mt_res = await asyncio.wait_for(
                resolve_username_via_mtproto(resolved_uname),
                timeout=2.4 if fetch_avatar else 1.6,
            )
            if mt_res:
                mt_kind, mt_uid, mt_un, mt_name = mt_res
                if mt_kind == "CHAT" and not in_scam and not in_guar:
                    return (
                        False,
                        "Группы и каналы не проверяются! Укажите личный аккаунт пользователя.",
                        None,
                        "",
                        [],
                        "",
                        None,
                    )
                if mt_kind == "BOT" and not in_scam and not in_guar:
                    return (
                        False,
                        "Боты не проверяются! Укажите аккаунт реального пользователя.",
                        None,
                        "",
                        [],
                        "",
                        None,
                    )
                if mt_kind == "USER" and mt_uid:
                    resolved_id = int(mt_uid)
                    verified_exists = True
                    if mt_un:
                        resolved_uname = mt_un
                    if mt_name and (not resolved_name or _is_placeholder_name(resolved_name, resolved_uname, resolved_id)):
                        resolved_name = mt_name
        except Exception as e:
            logger.debug("MTProto timeout/error for @%s: %s", resolved_uname, e)

    # 2.8 Поиск среди администраторов известных групп/каналов (TTL 10 мин)
    if not resolved_id and resolved_uname:
        await _cache_chat_admins_if_needed(bot, resolved_uname, max_chats=(5 if fetch_avatar else 2))
        adm_known = db_lookup_known_identity(username=resolved_uname)
        if adm_known["user_id"]:
            resolved_id = int(adm_known["user_id"])
            verified_exists = True
            if adm_known["full_name"] and (not resolved_name or _is_placeholder_name(resolved_name, resolved_uname, resolved_id)):
                resolved_name = adm_known["full_name"]

    # 3. Резервный запрос через канал пруфов и известные чаты (get_chat_member работает по ID, если юзер там есть)
    if resolved_id and (not resolved_uname or not resolved_name or not got_private_chat):
        proof_ch_id, _, _ = db_get_proof_channel()
        chat_candidates: List[int] = []
        if proof_ch_id:
            chat_candidates.append(int(proof_ch_id))
        extra_limit = 8 if fetch_avatar else 4
        for cid in _get_known_chat_ids()[:extra_limit]:
            if cid not in chat_candidates:
                chat_candidates.append(cid)

        for cid in chat_candidates:
            if resolved_uname and resolved_name and not _is_placeholder_name(resolved_name, resolved_uname, resolved_id):
                break
            try:
                cm = await bot.get_chat_member(cid, resolved_id)
                cm_user = getattr(cm, "user", None)
                if cm_user and not getattr(cm_user, "is_bot", False):
                    verified_exists = True
                    cm_uname = (getattr(cm_user, "username", None) or "").strip().lstrip("@").lower()
                    if cm_uname:
                        if resolved_uname and cm_uname != resolved_uname:
                            extra_usernames = _merge_username_aliases(cm_uname, resolved_uname, extra_usernames)
                        resolved_uname = cm_uname
                    cm_name = " ".join(p for p in (cm_user.first_name, cm_user.last_name) if p).strip()
                    if cm_name and (not resolved_name or _is_placeholder_name(resolved_name, resolved_uname, resolved_id)):
                        resolved_name = cm_name
            except Exception as e:
                logger.debug("get_chat_member(%s, %s): %s", cid, resolved_id, e)

    # 4. Загрузка аватара через Bot API по user_id
    if fetch_avatar and resolved_id and not avatar_bytes:
        try:
            photos = await bot.get_user_profile_photos(resolved_id, limit=1)
            if photos is not None:
                verified_exists = True
                if photos.total_count > 0 and photos.photos:
                    fid = photos.photos[0][-1].file_id
                    tg_file = await bot.get_file(fid)
                    bio = io.BytesIO()
                    await tg_file.download_to_memory(bio)
                    avatar_bytes = bio.getvalue()
        except Exception as e:
            logger.debug("get_user_profile_photos(%s): %s", resolved_id, e)

    # 5. Обогащение профиля и аватара через публичную страницу t.me/<username>
    if resolved_uname:
        tme_timeout = 5.0 if fetch_avatar else 1.8
        kind, pub_name, pub_avatar = await asyncio.to_thread(
            _inspect_public_tme_page,
            resolved_uname,
            fetch_avatar,
            tme_timeout,
        )
        if kind == "group_or_channel" and not got_private_chat and not in_scam and not in_guar and not resolved_id:
            return (
                False,
                "Группы и каналы не проверяются! Укажите личный аккаунт пользователя.",
                None,
                "",
                [],
                "",
                None,
            )
        if kind == "not_found" and not verified_exists:
            return (
                False,
                f"Пользователь <code>@{esc(resolved_uname)}</code> не найден в Telegram! Проверьте правильность юзернейма.",
                None,
                "",
                [],
                "",
                None,
            )
        if kind == "user":
            verified_exists = True
            if pub_name and (not resolved_name or _is_placeholder_name(resolved_name, resolved_uname, resolved_id)):
                resolved_name = pub_name
            if pub_avatar and not avatar_bytes:
                avatar_bytes = pub_avatar
        elif kind == "unknown" and re.fullmatch(r"[a-z][a-z0-9_]{2,34}", resolved_uname):
            verified_exists = True

    if not verified_exists:
        target_label = f"<code>@{esc(resolved_uname)}</code>" if resolved_uname else f"<code>{resolved_id}</code>"
        return (
            False,
            f"Пользователь {target_label} не найден или не существует в Telegram! Проверьте корректность данных.",
            None,
            "",
            [],
            "",
            None,
        )

    if fetch_avatar:
        if avatar_bytes:
            _save_avatar_cache(avatar_bytes, resolved_id, resolved_uname)
        else:
            avatar_bytes = _load_avatar_cache(resolved_id, resolved_uname)

    if resolved_id:
        db_upsert_user_cache(
            user_id=resolved_id,
            username=resolved_uname,
            extra_usernames=extra_usernames,
            full_name=resolved_name,
        )

    return True, "", resolved_id, resolved_uname, extra_usernames, resolved_name, avatar_bytes


def format_usernames_html(primary_uname: str, extra_usernames: List[str], max_extras: int = 5) -> str:
    primary = (primary_uname or "").strip().lstrip("@")
    extras = [u.strip().lstrip("@") for u in extra_usernames if u and u.strip().lstrip("@").lower() != primary.lower()]

    def _fmt_extras(lst: List[str]) -> str:
        shown = lst[:max_extras]
        hidden = len(lst) - len(shown)
        res = ", ".join(f"<code>@{esc(u)}</code>" for u in shown)
        if hidden > 0:
            res += f" <i>(+ещё {hidden})</i>"
        return res

    if primary and extras:
        return f"<code>@{esc(primary)}</code> <i>(доп: {_fmt_extras(extras)})</i>"
    if primary:
        return f"<code>@{esc(primary)}</code>"
    if extras:
        first = extras[0]
        rest = extras[1:]
        if rest:
            return f"<code>@{esc(first)}</code> <i>(доп: {_fmt_extras(rest)})</i>"
        return f"<code>@{esc(first)}</code>"
    return "<i>Не указаны</i>"


def format_permanent_links_html(
    user_id: Optional[int],
    username: str = "",
    extra_usernames: Optional[List[str]] = None,
) -> str:
    uname = (username or "").strip().lstrip("@")
    if not uname and extra_usernames:
        for ex in extra_usernames:
            ex_clean = (ex or "").strip().lstrip("@")
            if ex_clean:
                uname = ex_clean
                break

    parts: List[str] = []
    if user_id and int(user_id) > 0:
        uid = int(user_id)
        parts.append(f'<a href="tg://openmessage?user_id={uid}">Android</a>')
        parts.append(f'<a href="tg://user?id={uid}">iOS</a>')
        if uname:
            parts.append(f'<a href="https://t.me/{esc_attr(uname)}">t.me/{esc(uname)}</a>')
    elif uname:
        parts.append(f'<a href="https://t.me/{esc_attr(uname)}">t.me/{esc(uname)}</a>')
        parts.append(f'<a href="tg://resolve?domain={esc_attr(uname)}">Открыть чат</a>')

    if parts:
        return "  •  ".join(parts)
    return "<i>Ссылки недоступны</i>"


def get_uptime() -> str:
    seconds = int(time.time() - START_TIME)
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    if days > 0:
        return f"{days}д {hours}ч {minutes}м"
    return f"{hours}ч {minutes}м {secs}с"


# =====================================================================
# КЛАВИАТУРЫ (ОБЩЕЕ ГЛАВНОЕ МЕНЮ + АДМИН-ПАНЕЛЬ)
# =====================================================================
def get_user_main_kb(user_id: int) -> InlineKeyboardMarkup:
    rows = [
        [
            make_btn("Профиль", callback_data="my_profile", emoji_key="crown"),
            make_btn("Искать пользователя", callback_data="check_user_prompt", emoji_key="search"),
        ],
        [
            make_btn("Подать жалобу на скамера", callback_data="report_start", style="danger", emoji_key="siren"),
        ],
        [
            make_btn("Информация и ссылки", callback_data="info_links", emoji_key="eyes"),
        ],
    ]
    if is_full_admin(user_id):
        rows.append([
            make_btn("Админ-панель", callback_data="admin_panel", emoji_key="gear"),
        ])
    return InlineKeyboardMarkup(rows)


def get_admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            make_btn("Занести скамера", callback_data="scam_add_start", style="danger", emoji_key="plus"),
            make_btn("Добавить гаранта", callback_data="guar_add_start", style="success", emoji_key="shield"),
        ],
        [
            make_btn("Список скамеров", callback_data="scam_list:1", emoji_key="siren"),
            make_btn("Список гарантов", callback_data="guar_list:1", emoji_key="crown"),
        ],
        [
            make_btn("Модераторы", callback_data="adm_mods", emoji_key="shield"),
            make_btn("Канал пруфов", callback_data="adm_channel", emoji_key="eyes"),
        ],
        [
            make_btn("Выкачать данные", callback_data="adm_scrape_start", emoji_key="refresh"),
            make_btn("Статистика базы", callback_data="admin_stats", emoji_key="chart"),
        ],
        [
            make_btn("Главное меню", callback_data="main_home", emoji_key="gear"),
        ],
    ])


def get_cancel_fsm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_btn("Отмена", callback_data="fsm_cancel", style="danger", emoji_key="cross")],
    ])


def build_unverified_kb(
    target_key: str,
    likes: int,
    dislikes: int,
    add_payload: str,
    is_admin: bool = False,
    in_group: bool = False,
    user_id: Optional[int] = None,
    username: str = "",
) -> InlineKeyboardMarkup:
    rows = [
        [
            make_btn(f"Лайк ({likes})", callback_data=f"vote:like:{target_key}", style="success", emoji_key="check"),
            make_btn(f"Дизлайк ({dislikes})", callback_data=f"vote:dislike:{target_key}", style="danger", emoji_key="cross"),
        ],
    ]
    if in_group:
        bot_slug = BOT_USERNAME.lstrip("@")
        tok = _build_inline_start_token(user_id, username)
        rows.append([
            make_btn("Подать жалобу", url=f"https://t.me/{bot_slug}?start=rep_{tok}", style="danger", emoji_key="siren"),
            make_btn("Открыть в боте", url=f"https://t.me/{bot_slug}?start=chk_{tok}", emoji_key="search"),
        ])
        return InlineKeyboardMarkup(rows)

    rows.append([
        make_btn("Подать жалобу", callback_data=f"report_prefill:{target_key}", style="danger", emoji_key="siren"),
    ])
    if is_admin:
        rows.append([
            make_btn("Занести в скам-базу", callback_data=f"scam_quick_add:{add_payload}", emoji_key="siren"),
            make_btn("Сделать гарантом", callback_data=f"guar_quick_add:{add_payload}", emoji_key="shield"),
        ])
    rows.append([
        make_btn("Главное меню", callback_data="main_home", emoji_key="gear"),
    ])
    return InlineKeyboardMarkup(rows)


def build_scammer_kb(
    record_id: int,
    proof_url: str = "",
    is_admin: bool = False,
    proof_media_count: int = 0,
    in_group: bool = False,
    user_id: Optional[int] = None,
    username: str = "",
) -> InlineKeyboardMarkup:
    proof_row = []
    if proof_url:
        proof_row.append(make_btn("Ссылка на пруфы", url=proof_url, emoji_key="eyes"))
    if proof_media_count > 0:
        proof_row.append(
            make_btn(f"Пруфы ({proof_media_count} медиа)", callback_data=f"scam_proofs:{record_id}", emoji_key="eyes")
        )
    if not proof_row:
        proof_row.append(
            make_btn("Ссылка на пруфы", callback_data=f"no_proof:scam:{record_id}", emoji_key="eyes")
        )

    rows = [proof_row]
    if in_group:
        bot_slug = BOT_USERNAME.lstrip("@")
        tok = _build_inline_start_token(user_id, username)
        rows.append([make_btn("Открыть в боте", url=f"https://t.me/{bot_slug}?start=chk_{tok}", emoji_key="siren")])
        return InlineKeyboardMarkup(rows)

    if is_admin:
        rows.append([
            make_btn("Удалить из базы", callback_data=f"scam_del_ask:{record_id}", style="danger", emoji_key="trash"),
            make_btn("Список скамеров", callback_data="scam_list:1", emoji_key="siren"),
        ])
    rows.append([make_btn("Главное меню", callback_data="main_home", emoji_key="gear")])
    return InlineKeyboardMarkup(rows)


def build_guarantor_kb(
    record_id: int,
    is_admin: bool = False,
    target_key: str = "",
    likes: int = 0,
    dislikes: int = 0,
    in_group: bool = False,
    user_id: Optional[int] = None,
    username: str = "",
) -> InlineKeyboardMarkup:
    rows = []
    if target_key:
        rows.append([
            make_btn(f"Лайк ({likes})", callback_data=f"vote:like:{target_key}", style="success", emoji_key="check"),
            make_btn(f"Дизлайк ({dislikes})", callback_data=f"vote:dislike:{target_key}", style="danger", emoji_key="cross"),
        ])
    if in_group:
        bot_slug = BOT_USERNAME.lstrip("@")
        tok = _build_inline_start_token(user_id, username)
        rows.append([
            make_btn("Подать жалобу", url=f"https://t.me/{bot_slug}?start=rep_{tok}", style="danger", emoji_key="siren"),
            make_btn("Открыть в боте", url=f"https://t.me/{bot_slug}?start=chk_{tok}", emoji_key="crown"),
        ])
        return InlineKeyboardMarkup(rows)

    rows.append([
        make_btn(
            "Подать жалобу",
            callback_data=f"report_prefill:{target_key}" if target_key else "report_start",
            style="danger",
            emoji_key="siren",
        ),
    ])
    if is_admin:
        rows.append([
            make_btn("Удалить гаранта", callback_data=f"guar_del_ask:{record_id}", style="danger", emoji_key="trash"),
            make_btn("Список гарантов", callback_data="guar_list:1", emoji_key="crown"),
        ])
    rows.append([make_btn("Главное меню", callback_data="main_home", emoji_key="gear")])
    return InlineKeyboardMarkup(rows)


# =====================================================================
# ТЕКСТОВЫЕ ФОРМАТТЕРЫ ПРОФИЛЕЙ (С ЦИТАТАМИ, ШРИФТАМИ И ВОЗДУХОМ)
# =====================================================================
def build_scammer_caption(
    scam_row: sqlite3.Row,
    final_name: str,
    final_uname: str,
    merged_extras: List[str],
    final_id: Optional[int],
    is_dossier: bool = False,
) -> str:
    usernames_html = format_usernames_html(final_uname, merged_extras)
    id_html = f"<code>{final_id}</code>" if final_id else "<i>Скрыт (нет диалога с ботом)</i>"
    perm_links_html = format_permanent_links_html(final_id, final_uname, merged_extras)
    links_label = "Вечные ссылки" if final_id else "Ссылки на профиль"

    proof_url = (scam_row["proof_url"] or "").strip()
    media_items = _parse_media_json(scam_row["proof_media_json"] if "proof_media_json" in scam_row.keys() else "[]")

    if proof_url:
        proof_line = f'<a href="{esc_attr(proof_url)}">Открыть пост с доказательствами</a>'
    elif media_items:
        proof_line = f"<code>{len(media_items)}</code> <i>медиафайлов (кнопка ниже)</i>"
    elif scam_row["proof"]:
        proof_line = f"{esc(clip_text(scam_row['proof'], 110))} <i>(пока без ссылки)</i>"
    else:
        proof_line = "<i>Пока без ссылки</i>"

    title = (
        f"<b><u>ДОСЬЕ СКАМЕРА #{scam_row['id']}</u></b>"
        if is_dossier
        else f"<b><u>СТАТУС: СКАМЕР</u></b>  •  <code>ЗАПИСЬ #{scam_row['id']}</code>"
    )
    subtitle = f"<i>Проверка по базе {BOT_NAME}</i>"

    identity_quote = quote_block(
        f"{EMOJI['search']} <b>Имя:</b>  {esc(clip_text(final_name, 80))}\n"
        f"{EMOJI['eyes']} <b>Юзернеймы:</b>  {usernames_html}\n"
        f"{EMOJI['chart']} <b>Telegram ID:</b>  {id_html}\n"
        f"{EMOJI['lock']} <b>{links_label}:</b>  {perm_links_html}"
    )
    reason_safe = esc(clip_text(scam_row["reason"], 220))
    damage_safe = esc(clip_text(scam_row["damage"] or "Не указан", 80))
    case_quote = quote_block(
        f"{EMOJI['no_entry']} <b>Причина:</b>  <i>{reason_safe}</i>\n"
        f"{EMOJI['fire']} <b>Ущерб:</b>  <code>{damage_safe}</code>\n"
        f"{EMOJI['eyes']} <b>Пруфы:</b>  {proof_line}\n"
        f"{EMOJI['clock']} <b>Добавлен:</b>  <code>{esc(scam_row['added_at'])}</code>"
    )
    warn_footer = quote_block(
        f"{EMOJI['warn']} <i>Аккаунт занесён в список мошенников. Откажитесь от любых переводов и сделок с этим пользователем.</i>"
    )

    return f"{EMOJI['siren']} {title}\n{subtitle}\n\n{identity_quote}\n\n{case_quote}\n\n{warn_footer}"


def build_guarantor_caption(
    guar_row: sqlite3.Row,
    final_name: str,
    final_uname: str,
    merged_extras: List[str],
    final_id: Optional[int],
    is_dossier: bool = False,
    likes: int = 0,
    dislikes: int = 0,
) -> str:
    usernames_html = format_usernames_html(final_uname, merged_extras)
    id_html = f"<code>{final_id}</code>" if final_id else "<i>Скрыт (нет диалога с ботом)</i>"
    perm_links_html = format_permanent_links_html(final_id, final_uname, merged_extras)
    links_label = "Вечные ссылки" if final_id else "Ссылки на профиль"

    title = (
        f"<b><u>ДОСЬЕ ГАРАНТА #{guar_row['id']}</u></b>"
        if is_dossier
        else f"<b><u>СТАТУС: ПРОВЕРЕННЫЙ ГАРАНТ</u></b>  •  <code>#{guar_row['id']}</code>"
    )
    subtitle = f"<i>Официальный проверенный аккаунт {BOT_NAME}</i>"

    identity_quote = quote_block(
        f"{EMOJI['search']} <b>Имя:</b>  {esc(clip_text(final_name, 80))}\n"
        f"{EMOJI['eyes']} <b>Юзернеймы:</b>  {usernames_html}\n"
        f"{EMOJI['chart']} <b>Telegram ID:</b>  {id_html}\n"
        f"{EMOJI['lock']} <b>{links_label}:</b>  {perm_links_html}"
    )
    note_safe = esc(clip_text(guar_row["note"] or "Официальный проверенный гарант", 190))
    info_quote = quote_block(
        f"{EMOJI['shield']} <b>Информация:</b>  <i>{note_safe}</i>\n"
        f"{EMOJI['clock']} <b>Добавлен в базу:</b>  <code>{esc(guar_row['added_at'])}</code>"
    )
    tip_quote = quote_block(
        f"{EMOJI['check']} <i>Всегда сверяйте Telegram ID и вечные ссылки перед проведением сделки, чтобы не попасть на фейк.</i>"
    )
    rep_line = (
        f"{EMOJI['fire']} <b>Репутация:</b>  "
        f"{EMOJI['check']} <code>{likes}</code>  |  {EMOJI['cross']} <code>{dislikes}</code>"
    )
    return f"{EMOJI['crown']} {title}\n{subtitle}\n\n{identity_quote}\n\n{info_quote}\n\n{tip_quote}\n\n{rep_line}"


def build_unverified_caption(
    final_name: str,
    final_uname: str,
    merged_extras: List[str],
    final_id: Optional[int],
    likes: int,
    dislikes: int,
) -> str:
    usernames_html = format_usernames_html(final_uname, merged_extras)
    id_html = f"<code>{final_id}</code>" if final_id else "<i>Скрыт (нет диалога с ботом)</i>"
    perm_links_html = format_permanent_links_html(final_id, final_uname, merged_extras)
    links_label = "Вечные ссылки" if final_id else "Ссылки на профиль"

    identity_quote = quote_block(
        f"{EMOJI['search']} <b>Имя:</b>  {esc(clip_text(final_name, 80))}\n"
        f"{EMOJI['eyes']} <b>Юзернеймы:</b>  {usernames_html}\n"
        f"{EMOJI['chart']} <b>Telegram ID:</b>  {id_html}\n"
        f"{EMOJI['lock']} <b>{links_label}:</b>  {perm_links_html}"
    )
    warn_quote = quote_block(
        f"{EMOJI['warn']} <b>Профиль не найден в базе:</b>\n"
        f"<i>Пользователь не числится в списке проверенных гарантов и пока отсутствует в скам-базе. "
        f"Рекомендуем проводить любые сделки только через официального гаранта.</i>"
    )
    action_quote = quote_block(
        f"{EMOJI['siren']} <i>Если у вас есть доказательства мошенничества - воспользуйтесь кнопкой «Подать жалобу» ниже.</i>"
    )
    rep_line = (
        f"{EMOJI['fire']} <b>Репутация:</b>  "
        f"{EMOJI['check']} <code>{likes}</code>  |  {EMOJI['cross']} <code>{dislikes}</code>"
    )
    return (
        f"{EMOJI['shield']} <b><u>СТАТУС: НЕПРОВЕРЕННЫЙ</u></b>\n"
        f"<i>Проверка по базе {BOT_NAME}</i>\n\n"
        f"{identity_quote}\n\n"
        f"{warn_quote}\n\n"
        f"{action_quote}\n\n"
        f"{rep_line}"
    )


# =====================================================================
# ПРИВЕТСТВИЕ, ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ И УСЛОВИЯ ПОЛЬЗОВАНИЯ
# =====================================================================
def build_welcome_terms_text(full_mode: bool = False) -> str:
    intro = (
        f"{EMOJI['crown']} <b><u>ДОБРО ПОЖАЛОВАТЬ В {BOT_NAME}</u></b>\n"
        f"<code>{BOT_USERNAME}</code>  •  <i>Официальный антискам-бот</i>\n\n"
    )
    notice_quote = quote_block(
        f"{EMOJI['warn']} <b>Перед началом работы примите Политику конфиденциальности и Условия пользования.</b>\n\n"
        f"Это информационная база участников сделок. Данные в ней собираются на основе проверенных заявок и обращений, "
        f"поэтому в редких случаях информация может оказаться неточной или устаревшей - <b>но в любом случае база есть база</b>, "
        f"и решения о сделках вы принимаете самостоятельно на свой риск."
    )
    privacy_quote = quote_block(
        f"{EMOJI['lock']} <b><u>1. Политика конфиденциальности</u></b>\n\n"
        f"• Бот сохраняет ваш <code>Telegram ID</code>, публичный <code>@username</code>, отображаемое имя "
        f"и факт принятия настоящего соглашения.\n"
        f"• При проверке и подаче жалоб фиксируются идентификаторы проверяемых аккаунтов и приложенные доказательства.\n"
        f"• Конфиденциальные данные не передаются посторонним лицам, кроме публикации подтверждённых случаев скама в базу и канал пруфов.",
        expandable=not full_mode,
    )
    terms_quote = quote_block(
        f"{EMOJI['shield']} <b><u>2. Условия пользования базой</u></b>\n\n"
        f"• Сведения в <b>{BOT_NAME}</b> носят исключительно справочно-предупредительный характер.\n"
        f"• Администрация и модераторы проверяют жалобы добросовестно, но база может в отдельные моменты содержать неточности.\n"
        f"• Отсутствие человека в скам-базе не является гарантией его честности; наличие статуса проверяется пользователем самостоятельно.\n"
        f"• Запрещены фальсификация доказательств, ложные доносы и злоупотребление жалобами - за это доступ может быть ограничен.",
        expandable=not full_mode,
    )
    footer = (
        f"\n\n<i>Нажмите «Принять и продолжить», чтобы открыть главное меню, или «Перечитать политику и условия» для полного чтения:</i>"
        if not full_mode
        else f"\n\n<i>Вы открыли полную редакцию документа. При возникновении вопросов обратитесь к разделу «Информация и ссылки».</i>"
    )
    return f"{intro}{notice_quote}\n\n{privacy_quote}\n\n{terms_quote}{footer}"


def get_welcome_terms_kb(already_accepted: bool = False, full_mode: bool = False) -> InlineKeyboardMarkup:
    if already_accepted:
        return InlineKeyboardMarkup([
            [make_btn("Главное меню", callback_data="main_home", emoji_key="gear")],
            [make_btn("Информация и ссылки", callback_data="info_links", emoji_key="eyes")],
        ])
    rows = [
        [make_btn("Принять и продолжить", callback_data="accept_terms", style="success", emoji_key="check")],
    ]
    if not full_mode:
        rows.append([
            make_btn("Перечитать политику и условия", callback_data="reread_terms", emoji_key="eyes"),
        ])
    else:
        rows.append([
            make_btn("Свернуть описание", callback_data="reread_terms_short", emoji_key="refresh"),
        ])
    return InlineKeyboardMarkup(rows)


async def send_welcome_terms_prompt(target_message, user_id: int, full_mode: bool = False) -> None:
    accepted = db_has_accepted_terms(user_id)
    await safe_reply_text(
        target_message,
        build_welcome_terms_text(full_mode=full_mode),
        reply_markup=get_welcome_terms_kb(already_accepted=accepted, full_mode=full_mode),
    )


# =====================================================================
# ГЛАВНАЯ ФУНКЦИЯ ПРОВЕРКИ ПОЛЬЗОВАТЕЛЯ 24/7
# =====================================================================
async def perform_scam_check_and_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    q_id: Optional[int],
    q_uname: str,
    fwd_name: str = "",
    raw_query: str = "",
    validation_error: Optional[str] = None,
    in_group: bool = False,
) -> None:
    msg = update.effective_message
    checker = update.effective_user
    if not msg or not checker:
        return

    is_admin = is_full_admin(checker.id)
    was_search_mode = bool(
        (not in_group)
        and (
            context.user_data.pop("_awaiting_user_search", False)
            or getattr(msg, "users_shared", None)
            or getattr(msg, "user_shared", None)
        )
    )
    fallback_kb = (
        InlineKeyboardMarkup([[make_btn("Открыть бота", url=BOT_URL, emoji_key="crown")]])
        if in_group
        else get_user_main_kb(checker.id)
    )

    if validation_error:
        if was_search_mode:
            try:
                tmp_rm = await msg.reply_text(f"{EMOJI['warn']} <i>Обрабатываю...</i>", reply_markup=ReplyKeyboardRemove())
                await tmp_rm.delete()
            except Exception:
                pass
        if validation_error == "__EMPTY_GROUP_CHECK__":
            await safe_reply_text(
                msg,
                f"{EMOJI['search']} <b><u>Как проверить пользователя в группе</u></b>\n\n"
                + quote_block(
                    "• Напишите: <code>проверить @username</code> или <code>чек 123456789</code>\n"
                    "• Либо <b>ответьте (reply)</b> на сообщение человека словом <code>проверить</code> или <code>чек</code>!"
                ),
                reply_markup=fallback_kb,
            )
            return
        await safe_reply_text(
            msg,
            f"{EMOJI['no_entry']} <b><u>Проверка отклонена</u></b>\n\n"
            + quote_block(f"{EMOJI['warn']} <i>{esc(validation_error)}</i>"),
            reply_markup=fallback_kb,
        )
        return

    if not q_id and not q_uname:
        if was_search_mode:
            try:
                tmp_rm = await msg.reply_text(f"{EMOJI['search']} <i>Обрабатываю...</i>", reply_markup=ReplyKeyboardRemove())
                await tmp_rm.delete()
            except Exception:
                pass
        await safe_reply_text(
            msg,
            f"{EMOJI['warn']} <b><u>Не удалось распознать пользователя</u></b>\n\n"
            + quote_block(
                f"{EMOJI['search']} Отправьте в <b>{BOT_NAME}</b>:\n\n"
                f"• <code>@username</code> <i>(например,</i> <code>@durov</code><i>)</i>\n"
                f"• <b>Telegram ID</b> <i>(например,</i> <code>123456789</code><i>)</i>\n"
                f"• Ссылку <code>t.me/username</code> или <code>tg://user?id=...</code>\n"
                f"• <i>Перешлите сообщение или ответьте на сообщение командой</i> <code>проверить</code>."
            ),
            reply_markup=fallback_kb,
        )
        return

    wait_msg = None
    try:
        wait_msg = await msg.reply_text(
            f"{EMOJI['search']} <i>Сканирую базу <b>{BOT_NAME}</b>...</i>",
            reply_markup=ReplyKeyboardRemove() if was_search_mode else None,
        )
    except Exception:
        wait_msg = None

    known_pre = db_lookup_known_identity(user_id=q_id, username=q_uname)
    scam_row = db_find_scammer(user_id=q_id or known_pre["user_id"], username=q_uname, extra_usernames=known_pre["extra_usernames"])
    guar_row = None if scam_row else db_find_guarantor(
        user_id=q_id or known_pre["user_id"],
        username=q_uname,
        extra_usernames=known_pre["extra_usernames"],
    )

    active_row = scam_row or guar_row
    lookup_id = (active_row["user_id"] if (active_row and active_row["user_id"]) else None) or known_pre["user_id"] or q_id
    lookup_uname = q_uname or (active_row["username"] if (active_row and active_row["username"]) else "") or known_pre["username"]

    if wait_msg:
        await animate_status_steps(
            wait_msg,
            [f"{EMOJI['eyes']} <i>Загружаю профиль и аватар Telegram...</i>"],
            delay=0.22,
        )

    is_valid, val_err, tg_id, tg_uname, tg_extras, tg_name, avatar_bytes = await validate_and_resolve_user(
        context.bot, lookup_id, lookup_uname
    )

    if not is_valid:
        if wait_msg:
            try:
                await wait_msg.delete()
            except Exception:
                pass
        await safe_reply_text(
            msg,
            f"{EMOJI['no_entry']} <b><u>Проверка не выполнена</u></b>\n\n"
            + quote_block(f"{EMOJI['warn']} {val_err}"),
            reply_markup=fallback_kb,
        )
        return

    search_id = tg_id or lookup_id
    search_uname = tg_uname or lookup_uname
    if not scam_row and not guar_row:
        scam_row = db_find_scammer(
            user_id=search_id,
            username=search_uname,
            extra_usernames=tg_extras,
        )
        if not scam_row:
            guar_row = db_find_guarantor(
                user_id=search_id,
                username=search_uname,
                extra_usernames=tg_extras,
            )
        active_row = scam_row or guar_row

    final_id = tg_id or (active_row["user_id"] if active_row and active_row["user_id"] else None) or lookup_id
    final_uname = (tg_uname or (active_row["username"] if active_row and active_row["username"] else "") or lookup_uname or "").strip().lstrip("@").lower()
    stored_old_uname = (active_row["username"] if active_row and active_row["username"] else "").strip().lstrip("@").lower()
    stored_extras = _parse_extra_usernames(active_row["extra_usernames"]) if active_row else []
    merged_extras = _merge_username_aliases(
        final_uname,
        tg_extras,
        stored_extras,
        stored_old_uname if stored_old_uname and stored_old_uname != final_uname else "",
    )

    raw_row_name = active_row["full_name"] if active_row else ""
    if tg_name and not _is_placeholder_name(tg_name, final_uname, final_id):
        final_name = tg_name
    elif fwd_name and not _is_placeholder_name(fwd_name, final_uname, final_id):
        final_name = fwd_name
    elif raw_row_name and not _is_placeholder_name(raw_row_name, final_uname, final_id):
        final_name = raw_row_name
    else:
        final_name = (
            tg_name
            or fwd_name
            or raw_row_name
            or (f"@{final_uname}" if final_uname else f"ID {final_id}")
        )

    if wait_msg:
        await animate_status_steps(
            wait_msg,
            [f"{EMOJI['fire']} <i>Собираю Liquid Glass карточку...</i>"],
            delay=0.18,
        )

    if scam_row:
        db_log_check(checker.id, raw_query or str(final_id or final_uname), result_type="scammer")
        existing_media_json = scam_row["proof_media_json"] if "proof_media_json" in scam_row.keys() else "[]"
        old_ex_str = _serialize_extra_usernames(stored_extras)
        new_ex_str = _serialize_extra_usernames(merged_extras)
        needs_enrich = bool(
            (final_id and not scam_row["user_id"])
            or (final_uname and final_uname != (scam_row["username"] or "").strip().lstrip("@").lower())
            or (new_ex_str and new_ex_str != old_ex_str)
            or (final_name and final_name != (scam_row["full_name"] or "") and not _is_placeholder_name(final_name, final_uname, final_id))
        )
        if needs_enrich:
            saved_scam_id = db_add_or_update_scammer(
                user_id=final_id,
                username=final_uname,
                full_name=final_name,
                reason=scam_row["reason"],
                proof=scam_row["proof"],
                damage=scam_row["damage"],
                added_by=scam_row["added_by"],
                extra_usernames=merged_extras,
                proof_url=scam_row["proof_url"] or "",
                proof_media_json=existing_media_json or "[]",
                preserve_added_at=True,
            )
            if saved_scam_id != scam_row["id"]:
                scam_row = db_get_scammer_by_id(saved_scam_id) or scam_row
                existing_media_json = scam_row["proof_media_json"] if "proof_media_json" in scam_row.keys() else "[]"

        card_bio = await generate_scammer_card_image(
            target_user_id=final_id,
            username=final_uname,
            full_name=final_name,
            reason=scam_row["reason"],
            damage=scam_row["damage"],
            added_at=scam_row["added_at"],
            case_id=scam_row["id"],
            avatar_bytes=avatar_bytes,
        )

        caption = build_scammer_caption(scam_row, final_name, final_uname, merged_extras, final_id)
        proof_url = (scam_row["proof_url"] or "").strip()
        media_cnt = len(_parse_media_json(existing_media_json))
        kb = build_scammer_kb(
            scam_row["id"],
            proof_url=proof_url,
            is_admin=is_admin,
            proof_media_count=media_cnt,
            in_group=in_group,
            user_id=final_id,
            username=final_uname,
        )

    elif guar_row:
        db_log_check(checker.id, raw_query or str(final_id or final_uname), result_type="guarantor")
        old_ex_str = _serialize_extra_usernames(stored_extras)
        new_ex_str = _serialize_extra_usernames(merged_extras)
        needs_enrich = bool(
            (final_id and not guar_row["user_id"])
            or (final_uname and final_uname != (guar_row["username"] or "").strip().lstrip("@").lower())
            or (new_ex_str and new_ex_str != old_ex_str)
            or (final_name and final_name != (guar_row["full_name"] or "") and not _is_placeholder_name(final_name, final_uname, final_id))
        )
        if needs_enrich:
            saved_guar_id = db_add_or_update_guarantor(
                user_id=final_id,
                username=final_uname,
                full_name=final_name,
                note=guar_row["note"],
                added_by=guar_row["added_by"],
                extra_usernames=merged_extras,
                preserve_added_at=True,
            )
            if saved_guar_id != guar_row["id"]:
                guar_row = db_get_guarantor_by_id(saved_guar_id) or guar_row

        card_bio = await generate_guarantor_card_image(
            target_user_id=final_id,
            username=final_uname,
            full_name=final_name,
            note=guar_row["note"],
            added_at=guar_row["added_at"],
            guar_id=guar_row["id"],
            avatar_bytes=avatar_bytes,
        )

        target_key = build_target_key(final_id, final_uname)
        likes, dislikes = db_get_votes(target_key)
        caption = build_guarantor_caption(
            guar_row,
            final_name,
            final_uname,
            merged_extras,
            final_id,
            likes=likes,
            dislikes=dislikes,
        )
        kb = build_guarantor_kb(
            guar_row["id"],
            is_admin=is_admin,
            target_key=target_key,
            likes=likes,
            dislikes=dislikes,
            in_group=in_group,
            user_id=final_id,
            username=final_uname,
        )

    else:
        db_log_check(checker.id, raw_query or str(final_id or final_uname), result_type="unverified")
        card_bio = await generate_unverified_card_image(
            target_user_id=final_id,
            username=final_uname,
            full_name=final_name,
            avatar_bytes=avatar_bytes,
        )

        target_key = build_target_key(final_id, final_uname)
        likes, dislikes = db_get_votes(target_key)
        add_payload = f"{final_id or ''}|{final_uname[:24]}"

        caption = build_unverified_caption(final_name, final_uname, merged_extras, final_id, likes, dislikes)
        kb = build_unverified_kb(
            target_key,
            likes,
            dislikes,
            add_payload,
            is_admin=is_admin,
            in_group=in_group,
            user_id=final_id,
            username=final_uname,
        )

    if wait_msg:
        try:
            await wait_msg.delete()
        except Exception:
            pass

    await safe_reply_photo(msg, photo=card_bio, caption=caption, reply_markup=kb)


def _build_inline_start_token(user_id: Optional[int], username: str) -> str:
    if user_id and int(user_id) > 0:
        return f"id_{int(user_id)}"
    uname_clean = re.sub(r"[^A-Za-z0-9_]", "", (username or "").strip().lstrip("@"))[:50]
    return f"un_{uname_clean}" if uname_clean else "home"


def _parse_inline_start_arg(arg: str) -> Tuple[str, Optional[int], str]:
    raw = (arg or "").strip()
    if raw.startswith("chk_"):
        mode, body = "chk", raw[4:]
    elif raw.startswith("rep_"):
        mode, body = "rep", raw[4:]
    else:
        return "", None, ""

    if body.startswith("id_") and body[3:].isdigit():
        return mode, int(body[3:]), ""
    if body.startswith("un_") and body[3:]:
        return mode, None, body[3:].strip().lstrip("@").lower()
    return "", None, ""


def build_inline_result_kb(
    status_kind: str,
    target_key: str,
    user_id: Optional[int],
    username: str,
    proof_url: str = "",
    likes: int = 0,
    dislikes: int = 0,
) -> InlineKeyboardMarkup:
    bot_slug = BOT_USERNAME.lstrip("@")
    tok = _build_inline_start_token(user_id, username)
    chk_url = f"https://t.me/{bot_slug}?start=chk_{tok}"
    rep_url = f"https://t.me/{bot_slug}?start=rep_{tok}"

    rows: List[List[InlineKeyboardButton]] = []
    if status_kind == "scammer":
        if proof_url:
            rows.append([
                make_btn("Открыть пруфы", url=proof_url, style="danger", emoji_key="eyes"),
            ])
        rows.append([
            make_btn("Карточка и досье в боте", url=chk_url, emoji_key="siren"),
        ])
    elif status_kind == "guarantor":
        rows.append([
            make_btn(f"Лайк ({likes})", callback_data=f"vote:like:{target_key}", style="success", emoji_key="check"),
            make_btn(f"Дизлайк ({dislikes})", callback_data=f"vote:dislike:{target_key}", style="danger", emoji_key="cross"),
        ])
        rows.append([
            make_btn("Карточка в боте", url=chk_url, emoji_key="crown"),
            make_btn("Подать жалобу", url=rep_url, style="danger", emoji_key="siren"),
        ])
    else:
        rows.append([
            make_btn(f"Лайк ({likes})", callback_data=f"vote:like:{target_key}", style="success", emoji_key="check"),
            make_btn(f"Дизлайк ({dislikes})", callback_data=f"vote:dislike:{target_key}", style="danger", emoji_key="cross"),
        ])
        rows.append([
            make_btn("Проверить в боте", url=chk_url, emoji_key="search"),
            make_btn("Подать жалобу", url=rep_url, style="danger", emoji_key="siren"),
        ])
    return InlineKeyboardMarkup(rows)


def _make_inline_text_content(html_text: str) -> InputTextMessageContent:
    msg_txt = html_text if len(html_text) <= 4096 else (html_text[:4080] + "\n<i>...</i>")
    _itm_params = inspect.signature(InputTextMessageContent.__init__).parameters
    kwargs: Dict[str, Any] = {
        "message_text": msg_txt,
        "parse_mode": ParseMode.HTML,
    }
    if "link_preview_options" in _itm_params and LinkPreviewOptions is not None:
        kwargs["link_preview_options"] = LinkPreviewOptions(is_disabled=True)
    elif "disable_web_page_preview" in _itm_params:
        kwargs["disable_web_page_preview"] = True
    return InputTextMessageContent(**kwargs)


def _strip_markup_icons_or_styles(markup: Any, strip_icons: bool = True, strip_styles: bool = False) -> Any:
    if not isinstance(markup, InlineKeyboardMarkup):
        return markup
    new_rows: List[List[InlineKeyboardButton]] = []
    for row in markup.inline_keyboard:
        new_row: List[InlineKeyboardButton] = []
        for btn in row:
            style = None if strip_styles else (
                getattr(btn, "style", None) or (getattr(btn, "api_kwargs", None) or {}).get("style")
            )
            icon_id = None if strip_icons else (
                getattr(btn, "icon_custom_emoji_id", None)
                or (getattr(btn, "api_kwargs", None) or {}).get("icon_custom_emoji_id")
            )
            btn_kwargs: Dict[str, Any] = {"text": btn.text}
            if btn.callback_data is not None:
                btn_kwargs["callback_data"] = btn.callback_data[:64]
            elif btn.url is not None:
                btn_kwargs["url"] = btn.url
            api_kw: Dict[str, Any] = {}
            if style in ("primary", "success", "danger"):
                if _SUPPORTS_NATIVE_STYLE:
                    btn_kwargs["style"] = style
                else:
                    api_kw["style"] = style
            if icon_id:
                if _SUPPORTS_NATIVE_ICON:
                    btn_kwargs["icon_custom_emoji_id"] = icon_id
                else:
                    api_kw["icon_custom_emoji_id"] = icon_id
            if api_kw:
                btn_kwargs["api_kwargs"] = api_kw
            new_row.append(InlineKeyboardButton(**btn_kwargs))
        new_rows.append(new_row)
    return InlineKeyboardMarkup(new_rows)


def _rebuild_inline_results_without_icons(
    results: List[InlineQueryResultArticle],
    strip_style: bool = False,
) -> List[InlineQueryResultArticle]:
    clean_res: List[InlineQueryResultArticle] = []
    for r in results:
        rm = _strip_markup_icons_or_styles(
            getattr(r, "reply_markup", None),
            strip_icons=True,
            strip_styles=strip_style,
        )
        clean_res.append(
            InlineQueryResultArticle(
                id=r.id,
                title=r.title,
                description=getattr(r, "description", None),
                input_message_content=r.input_message_content,
                reply_markup=rm,
            )
        )
    return clean_res


async def _safe_answer_inline_query(
    inline_query,
    results: List[InlineQueryResultArticle],
    cache_time: int = 5,
    is_personal: bool = True,
    button_text: str = "Открыть KrakazeSkamBase",
    start_param: str = "inline",
) -> None:
    _ans_params = inspect.signature(inline_query.answer).parameters
    kwargs: Dict[str, Any] = {
        "results": results,
        "cache_time": cache_time,
        "is_personal": is_personal,
    }
    if "button" in _ans_params and InlineQueryResultsButton is not None:
        kwargs["button"] = InlineQueryResultsButton(text=button_text, start_parameter=start_param)
    elif "switch_pm_text" in _ans_params:
        kwargs["switch_pm_text"] = button_text
        kwargs["switch_pm_parameter"] = start_param

    try:
        await inline_query.answer(**kwargs)
    except BadRequest as e:
        err_l = str(e).lower()
        try:
            if "emoji" in err_l or "icon" in err_l or "style" in err_l:
                kwargs["results"] = _rebuild_inline_results_without_icons(
                    results,
                    strip_style=("style" in err_l),
                )
                await inline_query.answer(**kwargs)
            elif "button" in err_l or "switch_pm" in err_l:
                kwargs.pop("button", None)
                kwargs.pop("switch_pm_text", None)
                kwargs.pop("switch_pm_parameter", None)
                await inline_query.answer(**kwargs)
            else:
                logger.debug("inline_query.answer BadRequest: %s", e)
        except Exception as e2:
            logger.debug("inline_query.answer retry error: %s", e2)
    except Exception as e:
        logger.debug("inline_query.answer error: %s", e)


def _build_inline_profile_article(
    status_kind: str,
    final_id: Optional[int],
    final_uname: str,
    merged_extras: List[str],
    final_name: str,
    scam_row: Optional[sqlite3.Row] = None,
    guar_row: Optional[sqlite3.Row] = None,
    title_prefix: str = "",
) -> InlineQueryResultArticle:
    ident_short = f"@{final_uname}" if final_uname else f"ID {final_id}"
    if final_uname and final_id:
        ident_short = f"@{final_uname} • ID {final_id}"

    if status_kind == "scammer" and scam_row is not None:
        title = f"{title_prefix}🚨 СКАМЕР #{scam_row['id']} • {clip_text(final_name, 36)}"
        dmg = clip_text(scam_row["damage"] or "Подтверждённый скам", 36)
        rsn = clip_text(scam_row["reason"] or "Мошенничество", 65)
        description = f"{ident_short} | Ущерб: {dmg} - {rsn}"
        caption = build_scammer_caption(scam_row, final_name, final_uname, merged_extras, final_id)
        proof_url = (scam_row["proof_url"] or "").strip()
        kb = build_inline_result_kb(
            "scammer",
            target_key=build_target_key(final_id, final_uname),
            user_id=final_id,
            username=final_uname,
            proof_url=proof_url,
        )
    elif status_kind == "guarantor" and guar_row is not None:
        target_key = build_target_key(final_id, final_uname)
        likes, dislikes = db_get_votes(target_key)
        title = f"{title_prefix}👑 ГАРАНТ #{guar_row['id']} • {clip_text(final_name, 36)}"
        description = f"{ident_short} | Проверенный гарант • +{likes} / -{dislikes}"
        caption = build_guarantor_caption(
            guar_row, final_name, final_uname, merged_extras, final_id, likes=likes, dislikes=dislikes
        )
        kb = build_inline_result_kb(
            "guarantor",
            target_key=target_key,
            user_id=final_id,
            username=final_uname,
            likes=likes,
            dislikes=dislikes,
        )
    else:
        target_key = build_target_key(final_id, final_uname)
        likes, dislikes = db_get_votes(target_key)
        title = f"{title_prefix}🛡 НЕПРОВЕРЕННЫЙ • {clip_text(final_name, 36)}"
        description = f"{ident_short} | Нет в базе скамеров и гарантов • +{likes} / -{dislikes}"
        caption = build_unverified_caption(final_name, final_uname, merged_extras, final_id, likes, dislikes)
        kb = build_inline_result_kb(
            "unverified",
            target_key=target_key,
            user_id=final_id,
            username=final_uname,
            likes=likes,
            dislikes=dislikes,
        )

    art_seed = f"{status_kind}:{title_prefix}:{final_id or 0}:{final_uname}:{int(time.time() // 5)}"
    art_id = hashlib.md5(art_seed.encode("utf-8")).hexdigest()[:32]
    return InlineQueryResultArticle(
        id=art_id,
        title=title[:120],
        description=description[:160],
        input_message_content=_make_inline_text_content(caption),
        reply_markup=kb,
    )


async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработка inline-запросов в любом чате:
    пользователь вводит `@KrakazeBaseApp @username` или `@KrakazeBaseApp 123456789`
    и сразу видит статус + может отправить проверку в чат.
    """
    iq = update.inline_query
    if not iq or not iq.from_user:
        return

    checker = iq.from_user
    _cache_tg_user_obj(checker)
    raw_q = (iq.query or "").strip()

    # 1. Пустой запрос (@KrakazeBaseApp ) -> свой профиль + подсказка
    if not raw_q:
        my_id = checker.id
        my_uname = (checker.username or "").strip().lstrip("@").lower()
        my_name = " ".join(p for p in (checker.first_name, checker.last_name) if p).strip() or (f"@{my_uname}" if my_uname else f"ID {my_id}")
        known_me = db_lookup_known_identity(user_id=my_id, username=my_uname)
        scam_me = db_find_scammer(user_id=my_id, username=my_uname, extra_usernames=known_me["extra_usernames"])
        guar_me = None if scam_me else db_find_guarantor(user_id=my_id, username=my_uname, extra_usernames=known_me["extra_usernames"])
        active_me = scam_me or guar_me
        extras_me = _merge_username_aliases(
            my_uname,
            known_me["extra_usernames"],
            _parse_extra_usernames(active_me["extra_usernames"]) if active_me else [],
        )
        me_kind = "scammer" if scam_me else ("guarantor" if guar_me else "unverified")
        me_article = _build_inline_profile_article(
            status_kind=me_kind,
            final_id=my_id,
            final_uname=my_uname,
            merged_extras=extras_me,
            final_name=my_name,
            scam_row=scam_me,
            guar_row=guar_me,
            title_prefix="👑 Мой профиль • ",
        )
        help_text = (
            f"{EMOJI['crown']} <b><u>{BOT_NAME}</u></b>  •  <code>{BOT_USERNAME}</code>\n"
            f"<i>Антискам-проверка прямо из любого чата</i>\n\n"
            + quote_block(
                f"{EMOJI['search']} Чтобы проверить пользователя в любом чате, напишите в строке ввода:\n"
                f"• <code>{BOT_USERNAME} @username</code>\n"
                f"• <code>{BOT_USERNAME} 123456789</code>"
            )
        )
        help_article = InlineQueryResultArticle(
            id="inline_help_empty",
            title="🔍 Введите @username или ID после юзернейма бота",
            description=f"Например: {BOT_USERNAME} @durov или {BOT_USERNAME} 123456789",
            input_message_content=_make_inline_text_content(help_text),
            reply_markup=InlineKeyboardMarkup([
                [make_btn("Открыть бота", url=BOT_URL, emoji_key="crown")],
            ]),
        )
        await _safe_answer_inline_query(iq, [me_article, help_article], cache_time=5)
        return

    # 2. Проверка на явные группы/каналы
    first_tok = raw_q.split()[0]
    if (
        re.search(r"t\.me/(?:\+|joinchat/|c/\d+)", raw_q, re.IGNORECASE)
        or re.search(r"tg://[A-Za-z0-9_]+\?(?:[^#\s]*&)?(?:user_id|chat_id|id)=-\d+", raw_q, re.IGNORECASE)
        or re.search(r"web\.telegram\.org/[a-z]/#-\d+", raw_q, re.IGNORECASE)
        or re.match(r"^-100\d+$", first_tok)
        or (first_tok.startswith("-") and first_tok[1:].isdigit())
    ):
        err_html = (
            f"{EMOJI['no_entry']} <b><u>Проверка отклонена</u></b>\n\n"
            + quote_block(f"{EMOJI['warn']} <i>Группы и каналы не проверяются! Укажите личный аккаунт пользователя.</i>")
        )
        err_art = InlineQueryResultArticle(
            id="inline_err_chat",
            title="⛔ Группы и каналы не проверяются",
            description="Укажите личный @username или числовой Telegram ID пользователя",
            input_message_content=_make_inline_text_content(err_html),
        )
        await _safe_answer_inline_query(iq, [err_art], cache_time=5)
        return

    q_id, q_uname = parse_user_query(raw_q)
    if not q_id and not q_uname:
        hint_html = (
            f"{EMOJI['search']} <b><u>Как проверить пользователя</u></b>\n\n"
            + quote_block(
                f"{EMOJI['fire']} Напишите в строке сообщения:\n"
                f"• <code>{BOT_USERNAME} @username</code>\n"
                f"• <code>{BOT_USERNAME} 123456789</code>"
            )
        )
        hint_art = InlineQueryResultArticle(
            id="inline_hint_parse",
            title="🔍 Введите корректный @username или ID",
            description="Пример: @durov, 123456789 или ссылка t.me/username",
            input_message_content=_make_inline_text_content(hint_html),
        )
        await _safe_answer_inline_query(iq, [hint_art], cache_time=2)
        return

    # 3. Поиск в базе и быстрый двусторонний резолв ID <-> @username
    known_pre = db_lookup_known_identity(user_id=q_id, username=q_uname)
    scam_row = db_find_scammer(user_id=q_id or known_pre["user_id"], username=q_uname, extra_usernames=known_pre["extra_usernames"])
    guar_row = None if scam_row else db_find_guarantor(
        user_id=q_id or known_pre["user_id"],
        username=q_uname,
        extra_usernames=known_pre["extra_usernames"],
    )
    active_row = scam_row or guar_row

    lookup_id = (active_row["user_id"] if (active_row and active_row["user_id"]) else None) or known_pre["user_id"] or q_id
    lookup_uname = q_uname or (active_row["username"] if (active_row and active_row["username"]) else "") or known_pre["username"]

    is_valid = True
    val_err = ""
    tg_id: Optional[int] = lookup_id
    tg_uname: str = lookup_uname
    tg_extras: List[str] = list(known_pre["extra_usernames"])
    tg_name: str = known_pre["full_name"]

    try:
        is_valid, val_err, tg_id, tg_uname, tg_extras, tg_name, _ = await asyncio.wait_for(
            validate_and_resolve_user(context.bot, lookup_id, lookup_uname, fetch_avatar=False),
            timeout=4.5,
        )
    except asyncio.TimeoutError:
        tg_id = known_pre["user_id"] or lookup_id
        tg_uname = lookup_uname or known_pre["username"]
        tg_extras = known_pre["extra_usernames"]
        tg_name = known_pre["full_name"]
        is_valid = bool(tg_id or tg_uname)

    if not is_valid:
        plain_err = re.sub(r"<[^>]+>", "", val_err or "Пользователь не найден в Telegram")
        err_html = (
            f"{EMOJI['no_entry']} <b><u>Пользователь не найден</u></b>\n\n"
            + quote_block(f"{EMOJI['warn']} {val_err}")
        )
        err_art = InlineQueryResultArticle(
            id=f"inline_notfound_{hashlib.md5(raw_q.encode('utf-8')).hexdigest()[:16]}",
            title="❌ Пользователь не найден в Telegram",
            description=plain_err[:150],
            input_message_content=_make_inline_text_content(err_html),
        )
        await _safe_answer_inline_query(iq, [err_art], cache_time=4)
        return

    search_id = tg_id or lookup_id
    search_uname = tg_uname or lookup_uname
    if not scam_row and not guar_row:
        scam_row = db_find_scammer(user_id=search_id, username=search_uname, extra_usernames=tg_extras)
        if not scam_row:
            guar_row = db_find_guarantor(user_id=search_id, username=search_uname, extra_usernames=tg_extras)
        active_row = scam_row or guar_row

    final_id = tg_id or (active_row["user_id"] if active_row and active_row["user_id"] else None) or lookup_id
    final_uname = (tg_uname or (active_row["username"] if active_row and active_row["username"] else "") or lookup_uname or "").strip().lstrip("@").lower()
    stored_old_uname = (active_row["username"] if active_row and active_row["username"] else "").strip().lstrip("@").lower()
    stored_extras = _parse_extra_usernames(active_row["extra_usernames"]) if active_row else []
    merged_extras = _merge_username_aliases(
        final_uname,
        tg_extras,
        stored_extras,
        stored_old_uname if stored_old_uname and stored_old_uname != final_uname else "",
    )

    raw_row_name = active_row["full_name"] if active_row else ""
    if tg_name and not _is_placeholder_name(tg_name, final_uname, final_id):
        final_name = tg_name
    elif raw_row_name and not _is_placeholder_name(raw_row_name, final_uname, final_id):
        final_name = raw_row_name
    else:
        final_name = tg_name or raw_row_name or (f"@{final_uname}" if final_uname else f"ID {final_id}")

    if scam_row:
        db_log_check(checker.id, f"inline:{raw_q}", result_type="scammer")
        existing_media_json = scam_row["proof_media_json"] if "proof_media_json" in scam_row.keys() else "[]"
        old_ex_str = _serialize_extra_usernames(stored_extras)
        new_ex_str = _serialize_extra_usernames(merged_extras)
        needs_enrich = bool(
            (final_id and not scam_row["user_id"])
            or (final_uname and final_uname != (scam_row["username"] or "").strip().lstrip("@").lower())
            or (new_ex_str and new_ex_str != old_ex_str)
            or (final_name and final_name != (scam_row["full_name"] or "") and not _is_placeholder_name(final_name, final_uname, final_id))
        )
        if needs_enrich:
            saved_scam_id = db_add_or_update_scammer(
                user_id=final_id,
                username=final_uname,
                full_name=final_name,
                reason=scam_row["reason"],
                proof=scam_row["proof"],
                damage=scam_row["damage"],
                added_by=scam_row["added_by"],
                extra_usernames=merged_extras,
                proof_url=scam_row["proof_url"] or "",
                proof_media_json=existing_media_json or "[]",
                preserve_added_at=True,
            )
            if saved_scam_id != scam_row["id"]:
                scam_row = db_get_scammer_by_id(saved_scam_id) or scam_row
        status_kind = "scammer"
    elif guar_row:
        db_log_check(checker.id, f"inline:{raw_q}", result_type="guarantor")
        old_ex_str = _serialize_extra_usernames(stored_extras)
        new_ex_str = _serialize_extra_usernames(merged_extras)
        needs_enrich = bool(
            (final_id and not guar_row["user_id"])
            or (final_uname and final_uname != (guar_row["username"] or "").strip().lstrip("@").lower())
            or (new_ex_str and new_ex_str != old_ex_str)
            or (final_name and final_name != (guar_row["full_name"] or "") and not _is_placeholder_name(final_name, final_uname, final_id))
        )
        if needs_enrich:
            saved_guar_id = db_add_or_update_guarantor(
                user_id=final_id,
                username=final_uname,
                full_name=final_name,
                note=guar_row["note"],
                added_by=guar_row["added_by"],
                extra_usernames=merged_extras,
                preserve_added_at=True,
            )
            if saved_guar_id != guar_row["id"]:
                guar_row = db_get_guarantor_by_id(saved_guar_id) or guar_row
        status_kind = "guarantor"
    else:
        db_log_check(checker.id, f"inline:{raw_q}", result_type="unverified")
        status_kind = "unverified"

    article = _build_inline_profile_article(
        status_kind=status_kind,
        final_id=final_id,
        final_uname=final_uname,
        merged_extras=merged_extras,
        final_name=final_name,
        scam_row=scam_row,
        guar_row=guar_row,
    )
    await _safe_answer_inline_query(iq, [article], cache_time=5)


# =====================================================================
# ГЛАВНОЕ МЕНЮ И ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ
# =====================================================================
def build_main_home_text(user_id: int) -> str:
    stats = db_get_stats()

    summary_quote = quote_block(
        f"{EMOJI['siren']} <b>Скамеров в базе:</b>  <code>{stats['total_scammers']}</code>\n"
        f"{EMOJI['crown']} <b>Гарантов в базе:</b>  <code>{stats['total_guarantors']}</code>"
    )
    hint_quote = quote_block(
        f"{EMOJI['fire']} <b>Как проверить человека:</b>\n"
        f"• <i>Отправьте</i> <code>@username</code>, <b>ID</b>, <i>ссылку</i> <code>t.me/...</code> <i>или перешлите сообщение.</i>\n"
        f"• <i>В любом чате напишите</i> <code>{BOT_USERNAME} @username</code> <i>или</i> <code>{BOT_USERNAME} ID</code> <i>прямо в строке ввода!</i>"
    )
    return (
        f"{EMOJI['crown']} <b><u>{BOT_NAME}</u></b>  •  <code>{BOT_USERNAME}</code>\n"
        f"<i>Антискам-система и проверка репутации в Telegram</i>\n\n"
        f"{summary_quote}\n\n"
        f"{hint_quote}"
    )


async def send_main_menu_photo(target_message, user_id: int) -> None:
    card_bio = await generate_main_menu_card_image()
    await safe_reply_photo(
        target_message,
        photo=card_bio,
        caption=build_main_home_text(user_id),
        reply_markup=get_user_main_kb(user_id),
    )


async def send_search_user_prompt(
    target_message,
    context: ContextTypes.DEFAULT_TYPE,
    is_private: bool = True,
) -> None:
    if not target_message:
        return
    if is_private:
        context.user_data["_awaiting_user_search"] = True
        text = (
            f"{EMOJI['search']} <b><u>ПОИСК И ПРОВЕРКА ПОЛЬЗОВАТЕЛЯ</u></b>\n\n"
            + quote_block(
                f"Отправьте в чат любой идентификатор нужного человека:\n"
                f"• <code>@username</code> <i>(например,</i> <code>@durov</code><i>)</i>\n"
                f"• <code>123456789</code> - <b>Telegram ID</b>\n"
                f"• <code>t.me/username</code> или <code>tg://user?id=123456789</code>\n"
                f"• <i>Пересланное сообщение</i>\n\n"
                f"{EMOJI['crown']} <b>Либо нажмите кнопку «Выбрать пользователя» под строкой ввода,</b> "
                f"чтобы открыть список чатов Telegram и выбрать человека в 1 тап."
            )
        )
        await safe_reply_text(target_message, text, reply_markup=build_select_user_reply_kb())
    else:
        await safe_reply_text(
            target_message,
            f"{EMOJI['search']} Для поиска используйте личный чат с ботом: <code>/check @username</code>",
        )


async def _open_prefilled_report_from_id_or_uname(
    target_message,
    context: ContextTypes.DEFAULT_TYPE,
    q_id: Optional[int],
    q_uname: str,
) -> int:
    is_valid, _, tg_id, tg_uname, _, tg_name, _ = await validate_and_resolve_user(
        context.bot, q_id, q_uname, fetch_avatar=False
    )
    known_rep = db_lookup_known_identity(user_id=tg_id or q_id, username=tg_uname or q_uname)
    guar_row = db_find_guarantor(user_id=tg_id or q_id, username=tg_uname or q_uname)

    final_id = tg_id or known_rep["user_id"] or q_id
    final_uname = (tg_uname or known_rep["username"] or q_uname or "").lstrip("@")
    final_name = (
        tg_name
        or known_rep["full_name"]
        or (guar_row["full_name"] if guar_row and guar_row["full_name"] else "")
        or (f"@{final_uname}" if final_uname else f"ID {final_id}")
    )

    if not is_valid and not final_id and not final_uname:
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["rep_media"] = []
    context.user_data["rep_target_id"] = final_id
    context.user_data["rep_target_uname"] = final_uname
    context.user_data["rep_target_name"] = final_name

    uname_disp = f"@{final_uname}" if final_uname else f"ID {final_id}"
    await safe_reply_text(
        target_message,
        f"{EMOJI['siren']} <b><u>ПОДАЧА ЖАЛОБЫ НА СКАМЕРА</u></b>\n\n"
        f"{EMOJI['check']} <b>Нарушитель:</b> <b>{esc(final_name)}</b> (<code>{esc(uname_disp)}</code>)\n\n"
        + quote_block(
            f"<b>Шаг 2 из 3:</b> Подробно <b>опишите ситуацию</b> - как произошёл обман, "
            f"условия сделки и сумму ущерба:"
        ),
        reply_markup=get_cancel_fsm_kb(),
    )
    return REP_WAIT_DESC


async def start_or_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.effective_user:
        return ConversationHandler.END
    user = update.effective_user
    full_name = " ".join(p for p in (user.first_name, user.last_name) if p).strip()
    db_upsert_user_cache(user_id=user.id, username=user.username or "", full_name=full_name)
    db_record_started_user(user_id=user.id, username=user.username or "", full_name=full_name)
    was_search = bool(context.user_data.pop("_awaiting_user_search", False))
    deep_arg = context.args[0].strip() if context.args else ""
    context.user_data.clear()

    if was_search:
        try:
            tmp_rm = await update.message.reply_text(f"{EMOJI['gear']} <i>Открываю меню...</i>", reply_markup=ReplyKeyboardRemove())
            await tmp_rm.delete()
        except Exception:
            pass

    mode, dl_id, dl_uname = _parse_inline_start_arg(deep_arg)

    if not db_has_accepted_terms(user.id):
        if mode:
            context.user_data["_pending_start_arg"] = deep_arg
        await send_welcome_terms_prompt(update.message, user.id, full_mode=False)
        return ConversationHandler.END

    if mode == "chk" and (dl_id or dl_uname):
        await perform_scam_check_and_reply(
            update,
            context,
            q_id=dl_id,
            q_uname=dl_uname,
            raw_query=str(dl_id or dl_uname),
        )
        return ConversationHandler.END

    if mode == "rep" and (dl_id or dl_uname):
        return await _open_prefilled_report_from_id_or_uname(update.message, context, dl_id, dl_uname)

    await send_main_menu_photo(update.message, user.id)
    return ConversationHandler.END


async def check_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.effective_user:
        return ConversationHandler.END
    user = update.effective_user
    full_name = " ".join(p for p in (user.first_name, user.last_name) if p).strip()
    db_upsert_user_cache(user_id=user.id, username=user.username or "", full_name=full_name)

    is_priv = bool(update.effective_chat and update.effective_chat.type == ChatType.PRIVATE)
    if is_priv and not db_has_accepted_terms(user.id):
        await send_welcome_terms_prompt(update.message, user.id, full_mode=False)
        return ConversationHandler.END

    if context.args:
        raw_query = " ".join(context.args).strip()
        q_id, q_uname, fwd_name, val_err = extract_target_from_message(update.message, override_text=raw_query)
        await perform_scam_check_and_reply(
            update,
            context,
            q_id=q_id,
            q_uname=q_uname,
            fwd_name=fwd_name,
            raw_query=raw_query,
            validation_error=val_err,
            in_group=not is_priv,
        )
        return ConversationHandler.END

    if getattr(update.message, "reply_to_message", None):
        q_id, q_uname, fwd_name, val_err = _extract_reply_target_user(update.message.reply_to_message)
        await perform_scam_check_and_reply(
            update,
            context,
            q_id=q_id,
            q_uname=q_uname,
            fwd_name=fwd_name,
            raw_query=str(q_id or q_uname or "reply"),
            validation_error=val_err,
            in_group=not is_priv,
        )
        return ConversationHandler.END

    await send_search_user_prompt(update.message, context, is_private=is_priv)
    return ConversationHandler.END


async def profile_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    user = update.effective_user
    full_name = " ".join(p for p in (user.first_name, user.last_name) if p).strip()
    db_upsert_user_cache(user_id=user.id, username=user.username or "", full_name=full_name)

    if not db_has_accepted_terms(user.id):
        await send_welcome_terms_prompt(update.message, user.id, full_mode=False)
        return

    await perform_scam_check_and_reply(
        update,
        context,
        q_id=user.id,
        q_uname=(user.username or "").lower(),
        fwd_name=full_name,
        raw_query=str(user.id),
    )


async def set_api_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user or not update.effective_chat:
        return
    user = update.effective_user
    if not is_full_admin(user.id):
        await safe_reply_text(
            update.message,
            f"{EMOJI['cross']} Команда <code>/set_api</code> доступна только главным администраторам.",
        )
        return

    args = list(context.args or [])
    if not args:
        mt_ok, mt_msg = _is_mtproto_ready()
        api_id, api_hash = _get_mtproto_credentials()
        masked_hash = f"{api_hash[:4]}...{api_hash[-4:]}" if len(api_hash) >= 10 else ("задан" if api_hash else "нет")
        status_line = f"Активен ({mt_msg})" if mt_ok else f"Не готов ({mt_msg})"
        await safe_reply_text(
            update.message,
            f"{EMOJI['lock']} <b><u>Настройка определителя ID (MTProto)</u></b>\n\n"
            + quote_block(
                f"<b>Статус:</b>  <code>{esc(status_line)}</code>\n"
                f"<b>API_ID:</b>  <code>{api_id or 'нет'}</code>\n"
                f"<b>API_HASH:</b>  <code>{esc(masked_hash)}</code>\n\n"
                f"<i>Зачем это нужно: обычный Bot API не выдаёт Telegram ID незнакомых "
                f"пользователей, если они не заходили в бота и не находятся в общих группах. "
                f"После подключения MTProto (Telethon / Pyrogram) бот сможет находить ID любого "
                f"@username глобально.</i>"
            )
            + "\n\n<b>Команды:</b>\n"
            "• <code>/set_api API_ID API_HASH</code> (получить на my.telegram.org)\n"
            "• <code>/set_api clear</code> - удалить сохранённые ключи",
        )
        return

    if len(args) == 1 and args[0].strip().lower() in ("clear", "off", "reset", "delete", "удалить"):
        db_set_mtproto_credentials(None)
        await safe_reply_text(
            update.message,
            f"{EMOJI['check']} Ключи MTProto (<code>API_ID</code> / <code>API_HASH</code>) удалены из базы.",
        )
        return

    if len(args) < 2:
        await safe_reply_text(
            update.message,
            f"{EMOJI['warn']} Укажите оба параметра: <code>/set_api 12345678 abcdef1234567890abcdef1234567890</code>",
        )
        return

    raw_id = args[0].strip()
    raw_hash = args[1].strip()
    if not raw_id.isdigit() or int(raw_id) <= 0:
        await safe_reply_text(
            update.message,
            f"{EMOJI['cross']} Некорректный <code>API_ID</code>. Ожидается положительное число.",
        )
        return
    if len(raw_hash) < 16 or any(ch.isspace() for ch in raw_hash):
        await safe_reply_text(
            update.message,
            f"{EMOJI['cross']} Некорректный <code>API_HASH</code> (минимум 16 символов без пробелов).",
        )
        return

    db_set_mtproto_credentials(int(raw_id), raw_hash)
    try:
        await update.message.delete()
    except Exception:
        pass

    mt_ok, mt_msg = _is_mtproto_ready()
    extra_hint = (
        "\n<i>Определитель ID готов к глобальному поиску по @username!</i>"
        if mt_ok
        else f"\n{EMOJI['warn']} <i>Ключи сохранены, но {esc(mt_msg)}. Установите пакет:</i> <code>pip install telethon</code>"
    )
    await safe_send_message(
        context.bot,
        chat_id=update.effective_chat.id,
        text=(
            f"{EMOJI['check']} <b><u>MTProto API ключи сохранены!</u></b>\n\n"
            + quote_block(
                f"<b>API_ID:</b>  <code>{int(raw_id)}</code>\n"
                f"<b>Статус:</b>  <code>{esc(mt_msg)}</code>"
            )
            + extra_hint
        ),
    )


async def free_text_check_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    msg_obj = update.message
    if update.effective_user:
        _cache_tg_user_obj(update.effective_user)
    if getattr(msg_obj, "reply_to_message", None) and getattr(msg_obj.reply_to_message, "from_user", None):
        _cache_tg_user_obj(msg_obj.reply_to_message.from_user)
    if getattr(msg_obj, "forward_from", None):
        _cache_tg_user_obj(msg_obj.forward_from)
    fwd_org = getattr(msg_obj, "forward_origin", None)
    if fwd_org and getattr(fwd_org, "sender_user", None):
        _cache_tg_user_obj(fwd_org.sender_user)
    for new_m in (getattr(msg_obj, "new_chat_members", None) or []):
        _cache_tg_user_obj(new_m)
    if getattr(msg_obj, "left_chat_member", None):
        _cache_tg_user_obj(msg_obj.left_chat_member)
    for ent in (getattr(msg_obj, "entities", None) or getattr(msg_obj, "caption_entities", None) or []):
        if getattr(ent, "type", None) == "text_mention" and getattr(ent, "user", None):
            _cache_tg_user_obj(ent.user)

    if update.effective_chat and update.effective_chat.type != ChatType.PRIVATE:
        if update.effective_chat.type in (ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL):
            _record_known_chat_id(update.effective_chat.id)
        if update.effective_chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
            is_cmd, q_id, q_uname, fwd_name, raw_q, val_err = _extract_group_check_command(msg_obj)
            if is_cmd and update.effective_user:
                await perform_scam_check_and_reply(
                    update,
                    context,
                    q_id=q_id,
                    q_uname=q_uname,
                    fwd_name=fwd_name,
                    raw_query=raw_q,
                    validation_error=val_err,
                    in_group=True,
                )
        return
    if not update.effective_user:
        return
    user = update.effective_user

    if not db_has_accepted_terms(user.id):
        await send_welcome_terms_prompt(update.message, user.id, full_mode=False)
        return

    raw_text = (update.message.text or update.message.caption or "").strip()
    if raw_text.lower() in ("отмена", "❌ отмена", "назад", "отменить"):
        context.user_data.pop("_awaiting_user_search", None)
        try:
            rm_msg = await update.message.reply_text(
                f"{EMOJI['cross']} Поиск пользователя отменён.",
                reply_markup=ReplyKeyboardRemove(),
            )
            await asyncio.sleep(0.25)
            await rm_msg.delete()
        except Exception:
            pass
        await send_main_menu_photo(update.message, user.id)
        return

    # Если в ЛС тоже написали «проверить @username» или «чек @username» - отсекаем префикс команды
    is_prefix_cmd, g_id, g_uname, g_fname, g_raw, g_err = _extract_group_check_command(msg_obj)
    if is_prefix_cmd and g_err != "__EMPTY_GROUP_CHECK__":
        await perform_scam_check_and_reply(
            update,
            context,
            q_id=g_id,
            q_uname=g_uname,
            fwd_name=g_fname,
            raw_query=g_raw,
            validation_error=g_err,
        )
        return

    q_id, q_uname, fwd_name, val_err = extract_target_from_message(update.message)
    await perform_scam_check_and_reply(
        update,
        context,
        q_id=q_id,
        q_uname=q_uname,
        fwd_name=fwd_name,
        raw_query=raw_text,
        validation_error=val_err,
    )


# =====================================================================
# ПОЛЬЗОВАТЕЛЬСКАЯ ЖАЛОБА НА СКАМЕРА (СОЗДАНИЕ, РЕДАКТИРОВАНИЕ, ОТПРАВКА)
# =====================================================================
def build_report_preview_text(data: Dict[str, Any]) -> str:
    t_id = data.get("rep_target_id")
    t_uname = (data.get("rep_target_uname", "") or "").strip().lstrip("@")
    t_name = data.get("rep_target_name", "")
    desc = data.get("rep_desc", "")
    media_list: List[Dict[str, str]] = data.get("rep_media", [])

    photos_cnt = sum(1 for m in media_list if m.get("type") == "photo")
    videos_cnt = sum(1 for m in media_list if m.get("type") == "video")

    uname_html = f"<code>@{esc(t_uname)}</code>" if t_uname else "<i>Не указан</i>"
    id_html = f"<code>{t_id}</code>" if t_id else "<i>Скрыт</i>"
    links_html = format_permanent_links_html(t_id, t_uname)

    target_quote = quote_block(
        f"{EMOJI['search']} <b>Нарушитель:</b> <b>{esc(t_name or f'@{t_uname}' or f'ID {t_id}')}</b>\n"
        f"• <b>Юзернейм:</b> {uname_html}\n"
        f"• <b>Telegram ID:</b> {id_html}\n"
        f"• <b>Ссылки:</b> {links_html}"
    )
    desc_quote = quote_block(
        f"{EMOJI['no_entry']} <b>Описание ситуации:</b>\n<i>{esc(clip_text(desc, 1200))}</i>",
        expandable=len(desc) > 220,
    )
    media_quote = quote_block(
        f"{EMOJI['eyes']} <b>Прикреплённые доказательства:</b>\n"
        f"• Фото / скриншоты: <code>{photos_cnt}</code>\n"
        f"• Видеозаписи: <code>{videos_cnt}</code>"
    )

    return (
        f"{EMOJI['siren']} <b><u>АНКЕТА ЖАЛОБЫ НА СКАМЕРА</u></b>\n\n"
        f"{target_quote}\n\n"
        f"{desc_quote}\n\n"
        f"{media_quote}\n\n"
        f"<i>Проверьте данные и нажмите «Отправить заявку» ниже:</i>"
    )


def get_report_preview_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            make_btn("Отправить заявку", callback_data="rep_submit", style="success", emoji_key="check"),
        ],
        [
            make_btn("Изм. юзернейм", callback_data="rep_edit_target", emoji_key="search"),
            make_btn("Изм. описание", callback_data="rep_edit_desc", emoji_key="gear"),
        ],
        [
            make_btn("Изм. доказательства", callback_data="rep_edit_media", emoji_key="eyes"),
            make_btn("Отменить", callback_data="fsm_cancel", style="danger", emoji_key="cross"),
        ],
    ])


def get_report_media_step_kb(has_media: bool = False) -> InlineKeyboardMarkup:
    next_label = "Далее (к анкете)" if has_media else "Далее без медиа"
    return InlineKeyboardMarkup([
        [make_btn(next_label, callback_data="rep_media_done", style="success", emoji_key="check")],
        [make_btn("Отмена", callback_data="fsm_cancel", style="danger", emoji_key="cross")],
    ])


async def report_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.effective_user:
        return ConversationHandler.END
    user = update.effective_user
    if not db_has_accepted_terms(user.id):
        await send_welcome_terms_prompt(update.message, user.id, full_mode=False)
        return ConversationHandler.END

    was_search = bool(context.user_data.pop("_awaiting_user_search", False))
    context.user_data.clear()
    context.user_data["rep_media"] = []
    if was_search:
        try:
            tmp_rm = await update.message.reply_text(f"{EMOJI['siren']} <i>Подготовка анкеты...</i>", reply_markup=ReplyKeyboardRemove())
            await tmp_rm.delete()
        except Exception:
            pass

    text = (
        f"{EMOJI['siren']} <b><u>ПОДАЧА ЖАЛОБЫ НА СКАМЕРА</u></b>\n\n"
        + quote_block(
            f"<b>Шаг 1 из 3:</b> Отправьте <code>@username</code> нарушителя, его <b>Telegram ID</b> "
            f"или перешлите его личное сообщение.\n\n"
            f"<i>Группы, каналы, боты и несуществующие аккаунты отклоняются автоматически.</i>"
        )
    )
    await safe_reply_text(update.message, text, reply_markup=get_cancel_fsm_kb())
    return REP_WAIT_TARGET


async def report_start_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query or not update.effective_user:
        return ConversationHandler.END

    if not db_has_accepted_terms(update.effective_user.id):
        await query.answer("Сначала примите условия пользования", show_alert=True)
        if query.message:
            await send_welcome_terms_prompt(query.message, update.effective_user.id, full_mode=False)
        return ConversationHandler.END

    await query.answer()

    context.user_data.clear()
    context.user_data["rep_media"] = []

    text = (
        f"{EMOJI['siren']} <b><u>ПОДАЧА ЖАЛОБЫ НА СКАМЕРА</u></b>\n\n"
        + quote_block(
            f"<b>Шаг 1 из 3:</b> Отправьте <code>@username</code> нарушителя, его <b>Telegram ID</b> "
            f"или перешлите его личное сообщение.\n\n"
            f"<i>Группы, каналы, боты и несуществующие аккаунты отклоняются автоматически.</i>"
        )
    )
    await safe_reply_text(query.message, text, reply_markup=get_cancel_fsm_kb())
    return REP_WAIT_TARGET


async def report_prefill_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query or not update.effective_user:
        return ConversationHandler.END

    if not db_has_accepted_terms(update.effective_user.id):
        await query.answer("Сначала примите условия пользования", show_alert=True)
        if query.message:
            await send_welcome_terms_prompt(query.message, update.effective_user.id, full_mode=False)
        return ConversationHandler.END

    data = query.data or ""
    target_key = data.split(":", 1)[1] if ":" in data else ""
    q_id: Optional[int] = None
    q_uname: str = ""
    if target_key.startswith("id:"):
        try:
            q_id = int(target_key[3:])
        except ValueError:
            q_id = None
    elif target_key.startswith("un:"):
        q_uname = target_key[3:].strip().lstrip("@")

    if not q_id and not q_uname:
        return await report_start_cb(update, context)

    await query.answer("Открываю форму жалобы...")
    is_valid, _, tg_id, tg_uname, _, tg_name, _ = await validate_and_resolve_user(
        context.bot, q_id, q_uname
    )
    known_rep = db_lookup_known_identity(user_id=tg_id or q_id, username=tg_uname or q_uname)
    guar_row = db_find_guarantor(user_id=tg_id or q_id, username=tg_uname or q_uname)

    final_id = tg_id or known_rep["user_id"] or q_id
    final_uname = (tg_uname or known_rep["username"] or q_uname or "").lstrip("@")
    final_name = (
        tg_name
        or known_rep["full_name"]
        or (guar_row["full_name"] if guar_row and guar_row["full_name"] else "")
        or (f"@{final_uname}" if final_uname else f"ID {final_id}")
    )

    if not is_valid and not final_id and not final_uname:
        return await report_start_cb(update, context)

    context.user_data.clear()
    context.user_data["rep_media"] = []
    context.user_data["rep_target_id"] = final_id
    context.user_data["rep_target_uname"] = final_uname
    context.user_data["rep_target_name"] = final_name

    uname_disp = f"@{final_uname}" if final_uname else f"ID {final_id}"
    await safe_reply_text(
        query.message,
        f"{EMOJI['siren']} <b><u>ПОДАЧА ЖАЛОБЫ НА СКАМЕРА</u></b>\n\n"
        f"{EMOJI['check']} <b>Нарушитель:</b> <b>{esc(final_name)}</b> (<code>{esc(uname_disp)}</code>)\n\n"
        + quote_block(
            f"<b>Шаг 2 из 3:</b> Подробно <b>опишите ситуацию</b> - как произошёл обман, "
            f"условия сделки и сумму ущерба:"
        ),
        reply_markup=get_cancel_fsm_kb(),
    )
    return REP_WAIT_DESC


async def report_target_input(update: Update, context: ContextTypes.DEFAULT_TYPE, is_editing: bool = False) -> int:
    if not update.message:
        return REP_EDIT_TARGET if is_editing else REP_WAIT_TARGET

    q_id, q_uname, fwd_name, val_err = extract_target_from_message(update.message)
    if val_err:
        await safe_reply_text(
            update.message,
            f"{EMOJI['no_entry']} <b><u>Ошибка проверки</u></b>\n\n"
            + quote_block(f"{esc(val_err)}\n\n<i>Укажите личный</i> <code>@username</code> <i>или</i> <b>ID</b>:"),
            reply_markup=get_cancel_fsm_kb(),
        )
        return REP_EDIT_TARGET if is_editing else REP_WAIT_TARGET

    if not q_id and not q_uname:
        await safe_reply_text(
            update.message,
            f"{EMOJI['warn']} <b><u>Не удалось распознать пользователя</u></b>\n\n"
            + quote_block("<i>Напишите корректный</i> <code>@username</code> <i>или числовой</i> <b>ID</b>:"),
            reply_markup=get_cancel_fsm_kb(),
        )
        return REP_EDIT_TARGET if is_editing else REP_WAIT_TARGET

    wait_msg = await update.message.reply_text(f"{EMOJI['search']} <i>Проверяю существование пользователя...</i>")
    is_valid, err_text, tg_id, tg_uname, _, tg_name, _ = await validate_and_resolve_user(
        context.bot, q_id, q_uname
    )
    try:
        await wait_msg.delete()
    except Exception:
        pass

    if not is_valid:
        await safe_reply_text(
            update.message,
            f"{EMOJI['no_entry']} <b><u>Пользователь не найден</u></b>\n\n"
            + quote_block(f"{err_text}\n\n<i>Попробуйте ввести другой</i> <code>@username</code> <i>или</i> <b>ID</b>:"),
            reply_markup=get_cancel_fsm_kb(),
        )
        return REP_EDIT_TARGET if is_editing else REP_WAIT_TARGET

    final_id = tg_id or q_id
    final_uname = tg_uname or q_uname
    final_name = tg_name or fwd_name or (f"@{final_uname}" if final_uname else f"ID {final_id}")

    context.user_data["rep_target_id"] = final_id
    context.user_data["rep_target_uname"] = final_uname
    context.user_data["rep_target_name"] = final_name

    if is_editing:
        await safe_reply_text(
            update.message,
            build_report_preview_text(context.user_data),
            reply_markup=get_report_preview_kb(),
        )
        return REP_PREVIEW

    await safe_reply_text(
        update.message,
        f"{EMOJI['check']} <b>Пользователь подтверждён:</b> <b>{esc(final_name)}</b> "
        f"(<code>@{esc(final_uname or 'без_юзернейма')}</code>)\n\n"
        + quote_block(
            f"<b>Шаг 2 из 3:</b> Подробно <b>опишите ситуацию</b> - как произошёл обман, "
            f"условия сделки и сумму ущерба:"
        ),
        reply_markup=get_cancel_fsm_kb(),
    )
    return REP_WAIT_DESC


async def rep_target_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await report_target_input(update, context, is_editing=False)


async def rep_edit_target_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await report_target_input(update, context, is_editing=True)


async def rep_desc_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return REP_WAIT_DESC

    desc = update.message.text.strip()
    if len(desc) < 10:
        await safe_reply_text(
            update.message,
            f"{EMOJI['warn']} <b>Слишком короткое описание.</b>\n"
            + quote_block("<i>Расскажите подробнее о ситуации (минимум 10 символов):</i>"),
            reply_markup=get_cancel_fsm_kb(),
        )
        return REP_WAIT_DESC

    context.user_data["rep_desc"] = desc[:1500]
    context.user_data["rep_media"] = []
    context.user_data.pop("_rep_media_status_msg_id", None)

    sent = await safe_reply_text(
        update.message,
        f"{EMOJI['eyes']} <b><u>Шаг 3 из 3: Прикрепите доказательства</u></b>\n\n"
        + quote_block(
            f"Советуем скинуть <b>видео или скриншоты переписки</b>, подтверждающие факт мошенничества "
            f"(можно прислать сразу <b>альбомом</b> или по очереди до {MAX_REPORT_MEDIA} файлов).\n\n"
            f"<i>Когда закончите - нажмите кнопку «Далее» ниже:</i>"
        ),
        reply_markup=get_report_media_step_kb(has_media=False),
    )
    if sent:
        context.user_data["_rep_media_status_msg_id"] = sent.message_id
    return REP_WAIT_MEDIA


async def rep_edit_desc_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return REP_EDIT_DESC

    desc = update.message.text.strip()
    if len(desc) < 10:
        await safe_reply_text(
            update.message,
            f"{EMOJI['warn']} Описание слишком короткое. Напишите подробнее (от 10 символов):",
            reply_markup=get_cancel_fsm_kb(),
        )
        return REP_EDIT_DESC

    context.user_data["rep_desc"] = desc[:1500]
    await safe_reply_text(
        update.message,
        build_report_preview_text(context.user_data),
        reply_markup=get_report_preview_kb(),
    )
    return REP_PREVIEW


async def _update_media_collect_status(update: Update, context: ContextTypes.DEFAULT_TYPE, media_list: List[Dict[str, str]]) -> None:
    photos_cnt = sum(1 for m in media_list if m.get("type") == "photo")
    videos_cnt = sum(1 for m in media_list if m.get("type") == "video")
    text = (
        f"{EMOJI['check']} <b><u>Доказательства прикреплены</u></b>\n\n"
        + quote_block(
            f"• Фото / скриншоты: <code>{photos_cnt}</code>\n"
            f"• Видео: <code>{videos_cnt}</code>\n"
            f"• Всего файлов: <code>{len(media_list)}/{MAX_REPORT_MEDIA}</code>"
        )
        + "\n\n<i>Можете докинуть ещё файлы или нажать «Далее (к анкете)» (при отправке админам все фото придут вместе альбомом):</i>"
    )
    kb = get_report_media_step_kb(has_media=True)
    status_mid = context.user_data.get("_rep_media_status_msg_id")

    if status_mid and update.effective_chat:
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=int(status_mid),
                text=text,
                reply_markup=kb,
            )
            return
        except BadRequest as e:
            err = str(e).lower()
            if "message is not modified" in err:
                return
            if "emoji" in err or "icon" in err:
                try:
                    await context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=int(status_mid),
                        text=text,
                        reply_markup=rebuild_markup_without_icons(kb),
                    )
                    return
                except Exception:
                    pass
        except Exception:
            pass

    sent = await safe_reply_text(update.message, text, reply_markup=kb)
    if sent:
        context.user_data["_rep_media_status_msg_id"] = sent.message_id


async def rep_media_collect_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        return REP_WAIT_MEDIA

    media_list: List[Dict[str, str]] = context.user_data.setdefault("rep_media", [])

    if len(media_list) >= MAX_REPORT_MEDIA:
        await safe_reply_text(
            update.message,
            f"{EMOJI['warn']} Достигнут лимит вложений (<code>{MAX_REPORT_MEDIA}</code>). Нажмите «Далее (к анкете)»:",
            reply_markup=get_report_media_step_kb(has_media=True),
        )
        return REP_WAIT_MEDIA

    added = False
    if update.message.photo:
        media_list.append({"type": "photo", "file_id": update.message.photo[-1].file_id})
        added = True
    elif update.message.video:
        media_list.append({"type": "video", "file_id": update.message.video.file_id})
        added = True
    elif update.message.document:
        mime = (update.message.document.mime_type or "").lower()
        if mime.startswith("image/"):
            media_list.append({"type": "photo", "file_id": update.message.document.file_id})
            added = True
        elif mime.startswith("video/"):
            media_list.append({"type": "video", "file_id": update.message.document.file_id})
            added = True

    if added:
        await _update_media_collect_status(update, context, media_list)
        return REP_WAIT_MEDIA

    await safe_reply_text(
        update.message,
        f"{EMOJI['warn']} Отправьте <b>скриншот (фото)</b> или <b>видео</b> переписки, либо нажмите <b>«Далее»</b>:",
        reply_markup=get_report_media_step_kb(has_media=bool(media_list)),
    )
    return REP_WAIT_MEDIA


async def rep_preview_actions_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query or not update.effective_user:
        return ConversationHandler.END
    data = query.data or ""
    await query.answer()

    if data == "rep_media_done":
        context.user_data.pop("_rep_media_status_msg_id", None)
        await safe_reply_text(
            query.message,
            build_report_preview_text(context.user_data),
            reply_markup=get_report_preview_kb(),
        )
        return REP_PREVIEW

    if data == "rep_edit_target":
        await safe_reply_text(
            query.message,
            f"{EMOJI['search']} <b>Редактирование нарушителя</b>\n\n"
            + quote_block("<i>Введите новый</i> <code>@username</code> <i>или</i> <b>Telegram ID</b>:"),
            reply_markup=get_cancel_fsm_kb(),
        )
        return REP_EDIT_TARGET

    if data == "rep_edit_desc":
        await safe_reply_text(
            query.message,
            f"{EMOJI['gear']} <b>Редактирование описания</b>\n\n"
            + quote_block("<i>Введите новое описание ситуации:</i>"),
            reply_markup=get_cancel_fsm_kb(),
        )
        return REP_EDIT_DESC

    if data == "rep_edit_media":
        context.user_data["rep_media"] = []
        context.user_data.pop("_rep_media_status_msg_id", None)
        sent = await safe_reply_text(
            query.message,
            f"{EMOJI['eyes']} <b><u>Перезапись доказательств</u></b>\n\n"
            + quote_block(
                "Старые вложения очищены. Отправьте новые <b>скриншоты или видео переписки</b> "
                "(можно альбомом), затем нажмите <b>«Далее»</b>:"
            ),
            reply_markup=get_report_media_step_kb(has_media=False),
        )
        if sent:
            context.user_data["_rep_media_status_msg_id"] = sent.message_id
        return REP_WAIT_MEDIA

    if data == "rep_submit":
        user = update.effective_user
        rep_name = " ".join(p for p in (user.first_name, user.last_name) if p).strip() or f"ID {user.id}"
        target_id = context.user_data.get("rep_target_id")
        target_uname = context.user_data.get("rep_target_uname", "")
        target_name = context.user_data.get("rep_target_name", "")
        desc = context.user_data.get("rep_desc", "")
        media_list = context.user_data.get("rep_media", [])

        if query.message:
            await animate_status_steps(
                query.message,
                [
                    f"{EMOJI['clock']} <i>Сохраняю заявку и доказательства...</i>",
                    f"{EMOJI['shield']} <i>Передаю жалобу дежурному модератору...</i>",
                ],
                delay=0.28,
            )

        report_id = db_create_scam_report(
            reporter_id=user.id,
            reporter_username=user.username or "",
            reporter_name=rep_name,
            target_id=target_id,
            target_username=target_uname,
            target_name=target_name,
            description=desc,
            media_items=media_list,
        )

        # Выбираем случайного проверяющего (админ или модератор) с фолбэком на остальных
        shuffled_reviewers = get_all_reviewer_ids()
        random.shuffle(shuffled_reviewers)
        delivered = False
        for candidate_reviewer in shuffled_reviewers:
            if await dispatch_report_to_admin(context.bot, report_id, candidate_reviewer):
                delivered = True
                break

        context.user_data.clear()
        status_note = (
            f"{EMOJI['shield']} Ваша жалоба передана на проверку модератору.\n"
            f"{EMOJI['clock']} Вы получите уведомление сразу после принятия решения."
            if delivered
            else f"{EMOJI['clock']} Жалоба поставлена в очередь модерации и скоро будет передана на рассмотрение."
        )
        await safe_edit_text(
            query,
            f"{EMOJI['check']} <b><u>Заявка #{report_id} отправлена!</u></b>\n\n"
            + quote_block(status_note),
            reply_markup=InlineKeyboardMarkup([
                [make_btn("Главное меню", callback_data="main_home", emoji_key="gear")],
            ]),
        )
        return ConversationHandler.END

    return REP_PREVIEW


# =====================================================================
# ОТПРАВКА ЗАЯВКИ АДМИНУ (МЕДИА ВМЕСТЕ) И КРУГОВАЯ РОТАЦИЯ КАЖДЫЙ ЧАС
# =====================================================================
def build_admin_report_kb(report_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            make_btn("Принять", callback_data=f"rep_adm_accept:{report_id}", style="success", emoji_key="check"),
            make_btn("Отклонить", callback_data=f"rep_adm_reject:{report_id}", style="danger", emoji_key="cross"),
        ],
        [
            make_btn("Отклонить с причиной", callback_data=f"rep_adm_reject_reason:{report_id}", style="danger", emoji_key="no_entry"),
        ],
    ])


async def delete_previous_admin_report_messages(bot, admin_id: Optional[int], msg_ids: List[int]) -> None:
    if not admin_id or not msg_ids:
        return
    for mid in msg_ids:
        try:
            await bot.delete_message(chat_id=int(admin_id), message_id=int(mid))
        except Exception:
            pass


async def dispatch_report_to_admin(bot, report_id: int, admin_id: int) -> bool:
    """
    Отправляет заявку #report_id указанному администратору:
    1) Все фото/видео доказательства отправляются ВМЕСТЕ (send_media_group).
    2) Основная карточка заявки с кнопками Принять / Отклонить.
    """
    report = db_get_scam_report(report_id)
    if not report or report["status"] != "pending":
        return False

    media_items = _parse_media_json(report["media_json"])
    t_uname_clean = (report["target_username"] or "").strip().lstrip("@")
    t_uname = f"@{t_uname_clean}" if t_uname_clean else "нет username"
    t_id_num = report["target_id"] if report["target_id"] else None
    t_id_disp = str(t_id_num) if t_id_num else "Скрыт (нет диалога с ботом)"
    t_links_html = format_permanent_links_html(t_id_num, t_uname_clean)
    t_links_lbl = "Вечные ссылки" if t_id_num else "Ссылки на профиль"
    rep_uname = f"@{report['reporter_username']}" if report["reporter_username"] else "нет username"

    # 1. Отправляем все доказательства вместе в одном альбоме (с ID, юзернеймом и ссылками)
    album_caption = (
        f"{EMOJI['eyes']} <b>Доказательства к заявке #{report_id}</b> (<code>{len(media_items)}</code> файлов)\n"
        f"<b>Нарушитель:</b> <b>{esc(clip_text(report['target_name'] or t_uname, 50))}</b>\n"
        f"• Юзернейм: <code>{esc(t_uname)}</code>  •  Telegram ID: <code>{esc(t_id_disp)}</code>\n"
        f"• {t_links_lbl}: {t_links_html}"
    )
    sent_msg_ids = await send_media_album_safe(
        bot,
        chat_id=admin_id,
        media_items=media_items,
        caption_prefix=album_caption,
    )

    # 2. Отправляем основную карточку заявки с кнопками
    suspect_quote = quote_block(
        f"{EMOJI['search']} <b>Подозреваемый:</b> <b>{esc(report['target_name'])}</b>\n"
        f"• Юзернейм: <code>{esc(t_uname)}</code>\n"
        f"• Telegram ID: <code>{esc(t_id_disp)}</code>\n"
        f"• {t_links_lbl}: {t_links_html}"
    )
    reporter_quote = quote_block(
        f"{EMOJI['crown']} <b>Отправитель жалобы:</b> <b>{esc(report['reporter_name'])}</b>\n"
        f"• Юзернейм: <code>{esc(rep_uname)}</code>  •  ID: <code>{report['reporter_id']}</code>"
    )
    desc_quote = quote_block(
        f"{EMOJI['no_entry']} <b>Описание ситуации:</b>\n<i>{esc(clip_text(report['description'], 1500))}</i>",
        expandable=len(report["description"] or "") > 240,
    )

    text = (
        f"{EMOJI['siren']} <b><u>НОВАЯ ЖАЛОБА НА СКАМЕРА #{report_id}</u></b>\n\n"
        f"{suspect_quote}\n\n"
        f"{reporter_quote}\n\n"
        f"{desc_quote}\n\n"
        f"{EMOJI['eyes']} <b>Медиафайлов прикреплено:</b> <code>{len(media_items)}</code>\n"
        f"{EMOJI['clock']} <b>Таймер ответа:</b> <code>1 час</code> <i>(далее перейдёт следующему админу)</i>"
    )

    try:
        main_msg = await safe_send_message(
            bot,
            chat_id=admin_id,
            text=text,
            reply_markup=build_admin_report_kb(report_id),
        )
        if main_msg:
            sent_msg_ids.append(main_msg.message_id)
        db_update_report_assignment(report_id, admin_id, sent_msg_ids)
        return True
    except Exception as e:
        logger.error("Ошибка отправки заявки #%s администратору %s: %s", report_id, admin_id, e)
        await delete_previous_admin_report_messages(bot, admin_id, sent_msg_ids)
        return False


def pick_next_admin_round_robin(current_admin_id: Optional[int]) -> int:
    reviewers = get_all_reviewer_ids()
    if not reviewers:
        raise RuntimeError("Список проверяющих (ADMIN_IDS / moderators) пуст!")
    if len(reviewers) == 1:
        return reviewers[0]
    if current_admin_id in reviewers:
        idx = reviewers.index(current_admin_id)
        return reviewers[(idx + 1) % len(reviewers)]
    return random.choice(reviewers)


async def rotate_stale_reports_once(bot) -> None:
    now = time.time()
    pending = db_get_pending_reports()
    reviewers_count = max(1, len(get_all_reviewer_ids()))
    for rep in pending:
        assigned_at = float(rep["assigned_at"] or 0)
        if assigned_at <= 0 or (now - assigned_at) >= REPORT_ROTATION_SECONDS:
            old_admin = rep["assigned_admin_id"]
            try:
                old_msg_ids = json.loads(rep["admin_msg_ids_json"] or "[]")
            except Exception:
                old_msg_ids = []

            await delete_previous_admin_report_messages(bot, old_admin, old_msg_ids)

            candidate = pick_next_admin_round_robin(old_admin)
            tried = set()
            for _ in range(reviewers_count):
                if candidate in tried:
                    break
                tried.add(candidate)
                logger.info("Ротация заявки #%s: %s -> %s", rep["id"], old_admin, candidate)
                if await dispatch_report_to_admin(bot, int(rep["id"]), candidate):
                    break
                candidate = pick_next_admin_round_robin(candidate)


async def rotate_stale_reports_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    await rotate_stale_reports_once(context.bot)


async def _fallback_rotation_loop(bot) -> None:
    await asyncio.sleep(30)
    while True:
        try:
            await rotate_stale_reports_once(bot)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Ошибка в цикле ротации жалоб: %s", e)
        await asyncio.sleep(60)


def build_channel_message_link(channel_id: Optional[int], channel_username: str, message_id: int) -> str:
    uname = (channel_username or "").strip().lstrip("@")
    if uname:
        return f"https://t.me/{uname}/{int(message_id)}"
    if channel_id:
        raw = str(abs(int(channel_id)))
        internal_id = raw[3:] if raw.startswith("100") and len(raw) > 10 else raw
        return f"https://t.me/c/{internal_id}/{int(message_id)}"
    return ""


async def publish_report_proofs_to_channel(
    bot,
    report_id: int,
    report: sqlite3.Row,
    rec_id: int,
    extra_usernames: Optional[List[str]] = None,
) -> str:
    """
    Публикует принятый кейс с пруфами (фото/видео альбомом + причиной) в настроенный канал
    и возвращает прямую ссылку на опубликованный пост.
    """
    chan_id, chan_uname, _ = db_get_proof_channel()
    if not chan_id:
        return ""

    t_id = report["target_id"]
    t_uname = (report["target_username"] or "").strip().lstrip("@")
    t_name = report["target_name"] or (f"@{t_uname}" if t_uname else f"ID {t_id}")
    usernames_html = format_usernames_html(t_uname, extra_usernames or [])
    id_html = f"<code>{t_id}</code>" if t_id else "<i>Скрыт (нет диалога с ботом)</i>"
    perm_links_html = format_permanent_links_html(t_id, t_uname, extra_usernames or [])
    links_label = "Профиль по ID" if t_id else "Ссылки на профиль"
    reason_safe = esc(clip_text(report["description"], 440))
    now_str = datetime.now().strftime("%d.%m.%Y • %H:%M")

    post_text = (
        f"{EMOJI['siren']} <b><u>ПОДТВЕРЖДЁННЫЙ СКАМЕР  •  #{rec_id}</u></b>\n"
        f"<i>Официальный разбор по заявке</i> <code>#{report_id}</code>\n\n"
        + quote_block(
            f"{EMOJI['search']} <b>Профиль:</b>  <b>{esc(clip_text(t_name, 64))}</b>\n"
            f"{EMOJI['eyes']} <b>Юзернеймы:</b>  {usernames_html}\n"
            f"{EMOJI['chart']} <b>Telegram ID:</b>  {id_html}\n"
            f"{EMOJI['lock']} <b>{links_label}:</b>  {perm_links_html}"
        )
        + "\n\n"
        + quote_block(
            f"{EMOJI['no_entry']} <b>Причина занесения:</b>\n"
            f"<i>{reason_safe}</i>\n\n"
            f"{EMOJI['clock']} <b>Дата публикации:</b>  <code>{now_str}</code>"
        )
        + f"\n\n{EMOJI['shield']} <b>Проверить любого пользователя:</b>  <code>{BOT_USERNAME}</code>"
    )

    media_items = _parse_media_json(report["media_json"])
    plain_len = len(re.sub(r"<[^>]+>", "", post_text))
    ch_tok = _build_inline_start_token(t_id, t_uname)
    ch_kb = InlineKeyboardMarkup([
        [make_btn(f"Проверить в {BOT_NAME}", url=f"https://t.me/{BOT_USERNAME.lstrip('@')}?start=chk_{ch_tok}", style="primary", emoji_key="search")],
    ])

    try:
        if media_items:
            if plain_len <= 950:
                sent_ids = await send_media_album_safe(
                    bot,
                    chat_id=chan_id,
                    media_items=media_items,
                    caption_prefix=post_text,
                    reply_markup=ch_kb,
                )
                if sent_ids:
                    return build_channel_message_link(chan_id, chan_uname, sent_ids[0])
            else:
                album_proof_cap = (
                    f"{EMOJI['eyes']} <b>Доказательства по делу #{rec_id}</b> (<code>Заявка #{report_id}</code>)\n"
                    f"<b>Нарушитель:</b> <b>{esc(clip_text(t_name, 50))}</b>\n"
                    f"• Юзернеймы: {usernames_html}\n"
                    f"• Telegram ID: {id_html}\n"
                    f"• {links_label}: {perm_links_html}"
                )
                await send_media_album_safe(
                    bot,
                    chat_id=chan_id,
                    media_items=media_items,
                    caption_prefix=album_proof_cap,
                )
                msg = await safe_send_message(bot, chat_id=chan_id, text=post_text, reply_markup=ch_kb)
                if msg:
                    return build_channel_message_link(chan_id, chan_uname, msg.message_id)
        else:
            msg = await safe_send_message(bot, chat_id=chan_id, text=post_text, reply_markup=ch_kb)
            if msg:
                return build_channel_message_link(chan_id, chan_uname, msg.message_id)
    except Exception as e:
        logger.warning("Не удалось опубликовать пруфы в канал %s: %s", chan_id, e)
    return ""


async def admin_reject_reason_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text or not update.effective_user:
        return ADM_REJECT_REASON
    if not is_reviewer(update.effective_user.id):
        return ConversationHandler.END

    report_id = context.user_data.get("rejecting_report_id")
    if not report_id:
        return ConversationHandler.END

    reason_text = update.message.text.strip()[:500]
    report = db_get_scam_report(int(report_id))
    if not report or report["status"] != "pending":
        context.user_data.clear()
        await safe_reply_text(update.message, f"{EMOJI['warn']} Эта заявка уже была обработана.")
        return ConversationHandler.END

    try:
        old_msg_ids = json.loads(report["admin_msg_ids_json"] or "[]")
    except Exception:
        old_msg_ids = []
    await delete_previous_admin_report_messages(context.bot, report["assigned_admin_id"], old_msg_ids)

    db_finalize_report(int(report_id), status="rejected", admin_id=update.effective_user.id, reject_reason=reason_text)
    context.user_data.clear()

    try:
        await safe_send_message(
            context.bot,
            chat_id=int(report["reporter_id"]),
            text=(
                f"{EMOJI['cross']} <b><u>Ваша жалоба #{report_id} отклонена</u></b>\n\n"
                + quote_block(f"{EMOJI['no_entry']} <b>Причина отклонения:</b>\n<i>{esc(reason_text)}</i>")
            ),
        )
    except Exception:
        pass

    back_kb = (
        get_admin_panel_kb()
        if is_full_admin(update.effective_user.id)
        else InlineKeyboardMarkup([[make_btn("Главное меню", callback_data="main_home", emoji_key="gear")]])
    )
    await safe_reply_text(
        update.message,
        f"{EMOJI['cross']} <b>Заявка #{report_id} отклонена</b>\n\n"
        + quote_block(f"<i>{esc(reason_text)}</i>"),
        reply_markup=back_kb,
    )
    return ConversationHandler.END


# =====================================================================
# АДМИНСКИЙ ДИАЛОГ ДОБАВЛЕНИЯ СКАМЕРА / ГАРАНТА / МОДЕРАТОРА / КАНАЛА / FIREBASE
# =====================================================================
async def fsm_start_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query or not update.effective_user:
        return ConversationHandler.END
    user_id = update.effective_user.id
    data = query.data or ""

    if data.startswith("rep_adm_reject_reason:"):
        if not is_reviewer(user_id):
            await query.answer("Доступ разрешён только администраторам и модераторам!", show_alert=True)
            return ConversationHandler.END
        await query.answer()
        context.user_data.clear()
        report_id = int(data.split(":", 1)[1])
        report = db_get_scam_report(report_id)
        if not report or report["status"] != "pending":
            await safe_reply_text(query.message, f"{EMOJI['warn']} Эта заявка уже обработана.")
            return ConversationHandler.END

        context.user_data["rejecting_report_id"] = report_id
        await safe_reply_text(
            query.message,
            f"{EMOJI['no_entry']} <b><u>Отклонение заявки #{report_id}</u></b>\n\n"
            + quote_block("<i>Напишите причину отклонения - она будет отправлена автору жалобы:</i>"),
            reply_markup=get_cancel_fsm_kb(),
        )
        return ADM_REJECT_REASON

    if not is_full_admin(user_id):
        await query.answer("Доступ разрешён только главным администраторам!", show_alert=True)
        return ConversationHandler.END

    await query.answer()
    context.user_data.clear()

    if data == "adm_scrape_start":
        scrape_kb = InlineKeyboardMarkup([
            [make_btn(f"Выкачать @{INITIAL_SEED_CHANNEL}", callback_data="adm_scrape_default", style="success", emoji_key="refresh")],
            [make_btn("Отмена", callback_data="fsm_cancel", style="danger", emoji_key="cross")],
        ])
        await safe_reply_text(
            query.message,
            f"{EMOJI['refresh']} <b><u>ВЫКАЧАТЬ ДАННЫЕ ИЗ КАНАЛА</u></b>\n\n"
            + quote_block(
                "Отправьте ссылку на открытый Telegram-канал (например, <code>https://t.me/loneasproofs</code>) "
                "или его <code>@username</code>.\n\n"
                "<i>Бот выкачает все сообщения с доказательствами, даже не находясь в этом канале, "
                "извлечёт ID / юзернеймы / причины и сохранит базу в Firebase.</i>"
            ),
            reply_markup=scrape_kb,
        )
        return WAIT_SCRAPE_CHANNEL

    if data == "adm_fb_upload":
        await safe_reply_text(
            query.message,
            f"{EMOJI['refresh']} <b><u>Загрузка ключа Firebase JSON</u></b>\n\n"
            + quote_block(
                "Отправьте файл сервисного аккаунта Firebase (<code>.json</code>), содержащий поля "
                "<code>client_email</code> и <code>private_key</code>.\n\n"
                "<i>После загрузки бот автоматически подключится к Firestore и обновит синхронизацию</i> "
                f"<code>{esc(firebase_manager.collection_name)}/{esc(firebase_manager.doc_name)}</code>."
            ),
            reply_markup=get_cancel_fsm_kb(),
        )
        return WAIT_FB_JSON

    if data == "adm_mod_add":
        await safe_reply_text(
            query.message,
            f"{EMOJI['shield']} <b><u>Выдача роли модератора</u></b>\n\n"
            + quote_block(
                "Отправьте <code>@username</code>, <b>Telegram ID</b> или перешлите личное сообщение пользователя.\n\n"
                "<i>Модератор сможет получать и рассматривать только входящие заявки на скамеров (без доступа к админ-панели).</i>"
            ),
            reply_markup=get_cancel_fsm_kb(),
        )
        return WAIT_MOD_TARGET

    if data == "adm_channel_set":
        await safe_reply_text(
            query.message,
            f"{EMOJI['eyes']} <b><u>Привязка канала пруфов</u></b>\n\n"
            + quote_block(
                "Добавьте бота в нужный канал со всеми правами администратора - он определится автоматически.\n\n"
                "<i>Или укажите канал вручную:</i> перешлите любой пост из канала, отправьте <code>@channel</code> или ID <code>-100...</code>:"
            ),
            reply_markup=get_cancel_fsm_kb(),
        )
        return WAIT_CHANNEL_SET

    if data.startswith("scam_quick_add:"):
        payload = data.split(":", 1)[1]
        parts = payload.split("|", 1)
        q_id = int(parts[0]) if parts[0].isdigit() else None
        q_uname = parts[1].strip() if len(parts) > 1 else ""
        _, _, tg_id, tg_uname, tg_extras, tg_name, _ = await validate_and_resolve_user(context.bot, q_id, q_uname)

        context.user_data["new_id"] = tg_id or q_id
        context.user_data["new_uname"] = tg_uname or q_uname
        context.user_data["new_extras"] = tg_extras
        context.user_data["new_name"] = tg_name or (f"@{tg_uname or q_uname}" if (tg_uname or q_uname) else f"ID {q_id}")

        await safe_reply_text(
            query.message,
            f"{EMOJI['siren']} <b><u>Занесение в скам-базу:</u></b> <code>{esc(context.user_data['new_name'])}</code>\n\n"
            + quote_block("<b>Шаг 1/3:</b> Введите <b>причину</b> занесения в скам-базу:"),
            reply_markup=get_cancel_fsm_kb(),
        )
        return WAIT_SCAM_REASON

    if data.startswith("guar_quick_add:"):
        payload = data.split(":", 1)[1]
        parts = payload.split("|", 1)
        q_id = int(parts[0]) if parts[0].isdigit() else None
        q_uname = parts[1].strip() if len(parts) > 1 else ""
        _, _, tg_id, tg_uname, tg_extras, tg_name, _ = await validate_and_resolve_user(context.bot, q_id, q_uname)

        context.user_data["new_id"] = tg_id or q_id
        context.user_data["new_uname"] = tg_uname or q_uname
        context.user_data["new_extras"] = tg_extras
        context.user_data["new_name"] = tg_name or (f"@{tg_uname or q_uname}" if (tg_uname or q_uname) else f"ID {q_id}")

        await safe_reply_text(
            query.message,
            f"{EMOJI['crown']} <b><u>Добавление в базу гарантов:</u></b> <code>{esc(context.user_data['new_name'])}</code>\n\n"
            + quote_block("<b>Шаг 1/1:</b> Введите <b>информацию о гаранте</b> (или <code>-</code>):"),
            reply_markup=get_cancel_fsm_kb(),
        )
        return WAIT_GUAR_NOTE

    if data == "guar_add_start":
        await safe_reply_text(
            query.message,
            f"{EMOJI['shield']} <b><u>Добавление нового гаранта в базу</u></b>\n\n"
            + quote_block("<b>Шаг 1/2:</b> Отправьте <code>@username</code>, <b>Telegram ID</b> или перешлите сообщение гаранта:"),
            reply_markup=get_cancel_fsm_kb(),
        )
        return WAIT_GUAR_TARGET

    await safe_reply_text(
        query.message,
        f"{EMOJI['plus']} <b><u>Занесение скамера в базу</u></b>\n\n"
        + quote_block("<b>Шаг 1/4:</b> Отправьте <code>@username</code>, <b>Telegram ID</b> или перешлите сообщение нарушителя:"),
        reply_markup=get_cancel_fsm_kb(),
    )
    return WAIT_SCAM_TARGET


async def scam_add_target_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        return WAIT_SCAM_TARGET

    q_id, q_uname, fwd_name, val_err = extract_target_from_message(update.message)
    if val_err:
        await safe_reply_text(update.message, f"{EMOJI['no_entry']} {val_err}", reply_markup=get_cancel_fsm_kb())
        return WAIT_SCAM_TARGET

    if not q_id and not q_uname:
        await safe_reply_text(
            update.message,
            f"{EMOJI['warn']} Некорректный ввод! Укажите <code>@username</code> или числовой <b>ID</b>:",
            reply_markup=get_cancel_fsm_kb(),
        )
        return WAIT_SCAM_TARGET

    is_valid, err_text, tg_id, tg_uname, tg_extras, tg_name, _ = await validate_and_resolve_user(
        context.bot, q_id, q_uname
    )
    if not is_valid:
        await safe_reply_text(update.message, f"{EMOJI['no_entry']} {err_text}", reply_markup=get_cancel_fsm_kb())
        return WAIT_SCAM_TARGET

    final_id = tg_id or q_id
    final_uname = tg_uname or q_uname
    final_name = tg_name or fwd_name or (f"@{final_uname}" if final_uname else f"ID {final_id}")

    context.user_data["new_id"] = final_id
    context.user_data["new_uname"] = final_uname
    context.user_data["new_extras"] = tg_extras
    context.user_data["new_name"] = final_name

    await safe_reply_text(
        update.message,
        f"{EMOJI['check']} Объект определён: <b>{esc(final_name)}</b> "
        f"(<code>{final_id or 'ID неизвестен'}</code> / <code>@{esc(final_uname or 'нет')}</code>)\n\n"
        + quote_block("<b>Шаг 2/4:</b> Опишите <b>причину</b> занесения в скам-базу:"),
        reply_markup=get_cancel_fsm_kb(),
    )
    return WAIT_SCAM_REASON


async def scam_add_reason_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return WAIT_SCAM_REASON
    context.user_data["new_reason"] = update.message.text.strip()[:300]
    await safe_reply_text(
        update.message,
        f"{EMOJI['fire']} <b>Шаг 3/4:</b> Укажите <b>сумму ущерба</b>\n"
        + quote_block("<i>Например:</i> <code>150,000 Stars</code>, <code>50 TON</code> <i>или</i> <code>Попытка скама</code>"),
        reply_markup=get_cancel_fsm_kb(),
    )
    return WAIT_SCAM_DAMAGE


async def scam_add_damage_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return WAIT_SCAM_DAMAGE
    context.user_data["new_damage"] = update.message.text.strip()[:100]
    await safe_reply_text(
        update.message,
        f"{EMOJI['eyes']} <b>Шаг 4/4:</b> Отправьте <b>ссылку на пруфы</b>\n"
        + quote_block("<code>https://...</code> / <code>t.me/...</code>, текстовое описание или <code>-</code> <i>(без ссылки)</i>"),
        reply_markup=get_cancel_fsm_kb(),
    )
    return WAIT_SCAM_PROOF


async def scam_add_proof_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.effective_user:
        return WAIT_SCAM_PROOF

    raw_proof = (update.message.text or "").strip()
    proof_url = extract_valid_url(raw_proof) if raw_proof != "-" else ""
    proof_text = "Пока без ссылки" if raw_proof == "-" else raw_proof[:300]

    s_id = context.user_data.get("new_id")
    s_uname = context.user_data.get("new_uname", "")
    s_extras = context.user_data.get("new_extras", [])
    s_name = context.user_data.get("new_name", "")
    s_reason = context.user_data.get("new_reason", "Мошенничество")
    s_damage = context.user_data.get("new_damage", "Не указан")

    rec_id = db_add_or_update_scammer(
        user_id=s_id,
        username=s_uname,
        full_name=s_name,
        reason=s_reason,
        proof=proof_text,
        damage=s_damage,
        added_by=update.effective_user.id,
        extra_usernames=s_extras,
        proof_url=proof_url,
    )

    _, _, _, _, _, _, avatar_bytes = await validate_and_resolve_user(context.bot, s_id, s_uname)
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    card_bio = await generate_scammer_card_image(
        target_user_id=s_id,
        username=s_uname,
        full_name=s_name,
        reason=s_reason,
        damage=s_damage,
        added_at=now_str,
        case_id=rec_id,
        avatar_bytes=avatar_bytes,
    )

    context.user_data.clear()
    await safe_reply_photo(
        update.message,
        photo=card_bio,
        caption=(
            f"{EMOJI['check']} <b><u>Запись #{rec_id} сохранена в скам-базе!</u></b>\n\n"
            + quote_block(f"{EMOJI['siren']} <i>При проверке этого пользователя 24/7 будет выдаваться эта красная карточка.</i>")
        ),
        reply_markup=build_scammer_kb(rec_id, proof_url=proof_url, is_admin=True),
    )
    return ConversationHandler.END


async def guar_add_target_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        return WAIT_GUAR_TARGET

    q_id, q_uname, fwd_name, val_err = extract_target_from_message(update.message)
    if val_err:
        await safe_reply_text(update.message, f"{EMOJI['no_entry']} {val_err}", reply_markup=get_cancel_fsm_kb())
        return WAIT_GUAR_TARGET

    if not q_id and not q_uname:
        await safe_reply_text(
            update.message,
            f"{EMOJI['warn']} Некорректный ввод! Укажите <code>@username</code> или числовой <b>ID</b>:",
            reply_markup=get_cancel_fsm_kb(),
        )
        return WAIT_GUAR_TARGET

    is_valid, err_text, tg_id, tg_uname, tg_extras, tg_name, _ = await validate_and_resolve_user(
        context.bot, q_id, q_uname
    )
    if not is_valid:
        await safe_reply_text(update.message, f"{EMOJI['no_entry']} {err_text}", reply_markup=get_cancel_fsm_kb())
        return WAIT_GUAR_TARGET

    final_id = tg_id or q_id
    final_uname = tg_uname or q_uname
    final_name = tg_name or fwd_name or (f"@{final_uname}" if final_uname else f"ID {final_id}")

    context.user_data["new_id"] = final_id
    context.user_data["new_uname"] = final_uname
    context.user_data["new_extras"] = tg_extras
    context.user_data["new_name"] = final_name

    await safe_reply_text(
        update.message,
        f"{EMOJI['check']} Гарант определён: <b>{esc(final_name)}</b> "
        f"(<code>{final_id or 'ID неизвестен'}</code> / <code>@{esc(final_uname or 'нет')}</code>)\n\n"
        + quote_block("<b>Шаг 2/2:</b> Введите <b>информацию / депозит</b> гаранта (или <code>-</code>):"),
        reply_markup=get_cancel_fsm_kb(),
    )
    return WAIT_GUAR_NOTE


async def guar_add_note_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text or not update.effective_user:
        return WAIT_GUAR_NOTE

    raw_note = update.message.text.strip()
    g_note = "Официальный проверенный гарант" if raw_note == "-" else raw_note[:200]

    g_id = context.user_data.get("new_id")
    g_uname = context.user_data.get("new_uname", "")
    g_extras = context.user_data.get("new_extras", [])
    g_name = context.user_data.get("new_name", "")

    rec_id = db_add_or_update_guarantor(
        user_id=g_id,
        username=g_uname,
        full_name=g_name,
        note=g_note,
        added_by=update.effective_user.id,
        extra_usernames=g_extras,
    )

    _, _, _, _, _, _, avatar_bytes = await validate_and_resolve_user(context.bot, g_id, g_uname)
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    card_bio = await generate_guarantor_card_image(
        target_user_id=g_id,
        username=g_uname,
        full_name=g_name,
        note=g_note,
        added_at=now_str,
        guar_id=rec_id,
        avatar_bytes=avatar_bytes,
    )

    context.user_data.clear()
    await safe_reply_photo(
        update.message,
        photo=card_bio,
        caption=(
            f"{EMOJI['check']} <b><u>Гарант #{rec_id} добавлен в базу!</u></b>\n\n"
            + quote_block(f"{EMOJI['crown']} <i>При проверке этого пользователя 24/7 будет выдаваться зелёная карточка гаранта.</i>")
        ),
        reply_markup=build_guarantor_kb(rec_id, is_admin=True),
    )
    return ConversationHandler.END


def build_mods_manage_view() -> Tuple[str, InlineKeyboardMarkup]:
    mods = db_get_moderators()
    btn_rows: List[List[InlineKeyboardButton]] = [
        [make_btn("Выдать модератора", callback_data="adm_mod_add", style="success", emoji_key="plus")],
    ]
    if not mods:
        text = (
            f"{EMOJI['shield']} <b><u>УПРАВЛЕНИЕ МОДЕРАТОРАМИ</u></b>\n\n"
            + quote_block(
                "Модераторы пока не назначены.\n\n"
                "<i>Модератор получает только входящие заявки на добавление скамеров и может "
                "принять или отклонить их. Доступ к админ-панели и управлению базой у него закрыт.</i>"
            )
        )
    else:
        lines = []
        for idx, m in enumerate(mods, start=1):
            uname = f"@{m['username']}" if m["username"] else "без username"
            name_disp = esc(clip_text(m["full_name"] or uname, 24))
            lines.append(
                f"{idx}. <b>{name_disp}</b>  •  <code>{esc(uname)}</code>  •  <code>ID {m['user_id']}</code>"
            )
            btn_rows.append([
                make_btn(
                    f"Снять: {m['full_name'] or uname}"[:38],
                    callback_data=f"adm_mod_del:{m['user_id']}",
                    emoji_key="trash",
                )
            ])
        text = (
            f"{EMOJI['shield']} <b><u>МОДЕРАТОРЫ ЗАЯВОК</u></b>  •  <code>Всего: {len(mods)}</code>\n\n"
            + quote_block("\n".join(lines))
            + "\n\n"
            + quote_block(
                "<i>Права модератора: только получение и рассмотрение входящих жалоб на скамеров.</i>"
            )
        )

    btn_rows.append([make_btn("Админ-панель", callback_data="admin_panel", emoji_key="gear")])
    return text, InlineKeyboardMarkup(btn_rows)


def build_channel_manage_view() -> Tuple[str, InlineKeyboardMarkup]:
    chan_id, chan_uname, chan_title = db_get_proof_channel()
    btn_rows: List[List[InlineKeyboardButton]] = [
        [make_btn("Указать канал вручную", callback_data="adm_channel_set", emoji_key="gear")],
    ]
    if chan_id:
        title_safe = esc(chan_title or "Канал пруфов")
        link_disp = f"<code>@{esc(chan_uname)}</code>" if chan_uname else f"<code>ID {chan_id}</code> (приватный)"
        text = (
            f"{EMOJI['eyes']} <b><u>КАНАЛ ПУБЛИКАЦИИ ПРУФОВ</u></b>\n\n"
            + quote_block(
                f"{EMOJI['check']} <b>Статус:</b>  <code>Подключён</code>\n"
                f"• <b>Название:</b>  <b>{title_safe}</b>\n"
                f"• <b>Адрес / ID:</b>  {link_disp}\n"
                f"• <b>Chat ID:</b>  <code>{chan_id}</code>"
            )
            + "\n\n"
            + quote_block(
                "<i>При принятии любой заявки на скамера бот автоматически публикует пост с пруфами "
                "в этот канал, копирует ссылку на сообщение и прикрепляет её к карточке скамера.</i>"
            )
        )
        btn_rows.append([make_btn("Отвязать канал", callback_data="adm_channel_clear", emoji_key="trash")])
    else:
        text = (
            f"{EMOJI['eyes']} <b><u>КАНАЛ ПУБЛИКАЦИИ ПРУФОВ</u></b>\n\n"
            + quote_block(
                f"{EMOJI['warn']} <b>Статус:</b>  <code>Не привязан</code>\n\n"
                "Добавьте бота <code>" + esc(BOT_USERNAME) + "</code> в нужный канал со всеми правами администратора - "
                "бот подключит канал автоматически.\n\n"
                "<i>Либо нажмите «Указать канал вручную» ниже и перешлите пост из канала.</i>"
            )
        )

    btn_rows.append([make_btn("Админ-панель", callback_data="admin_panel", emoji_key="gear")])
    return text, InlineKeyboardMarkup(btn_rows)


def build_firebase_manage_view() -> Tuple[str, InlineKeyboardMarkup]:
    db_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
    recs_total = firebase_manager._count_local_records(DB_PATH)
    conn_state = "Подключено" if firebase_manager.initialized else "Отключено"
    text = (
        f"{EMOJI['refresh']} <b><u>ОБЛАКО FIREBASE  •  {esc(firebase_manager.display_name.upper())}</u></b>\n\n"
        + quote_block(
            f"{EMOJI['check'] if firebase_manager.initialized else EMOJI['warn']} <b>Статус:</b>  <code>{conn_state}</code>\n"
            f"• <b>Проект:</b>  <code>{esc(firebase_manager.project_id)}</code>\n"
            f"• <b>Коллекция:</b>  <code>{esc(firebase_manager.collection_name)}</code>\n"
            f"• <b>Документ:</b>  <code>{esc(firebase_manager.doc_name)}</code>\n"
            f"• <b>Локальный файл:</b>  <code>{esc(DB_PATH.name)}</code> (<code>{db_size:,}</code> байт, <code>{recs_total}</code> записей)\n"
            f"• <b>Последняя синхронизация:</b>  <i>{esc(firebase_manager.last_sync_status)}</i>"
        )
        + "\n\n"
        + quote_block(
            "<i>База хранится в новой отдельной ячейке Firestore (telegram_scam_base) в виде сжатого "
            "архива base.db и автоматически синхронизируется каждые 60 сек + при выходе.</i>"
        )
    )
    kb = InlineKeyboardMarkup([
        [make_btn("Сохранить в облако сейчас", callback_data="adm_fb_sync", style="success", emoji_key="check")],
        [make_btn("Восстановить из облака", callback_data="adm_fb_restore", emoji_key="refresh")],
        [make_btn("Загрузить JSON ключ", callback_data="adm_fb_upload", emoji_key="lock")],
        [make_btn("Админ-панель", callback_data="admin_panel", emoji_key="gear")],
    ])
    return text, kb


async def firebase_json_upload_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.effective_user:
        return WAIT_FB_JSON
    if not is_full_admin(update.effective_user.id):
        return ConversationHandler.END

    doc = update.message.document
    if not doc or not (doc.file_name or "").lower().endswith(".json"):
        await safe_reply_text(
            update.message,
            f"{EMOJI['warn']} Отправьте именно файл сервисного аккаунта Firebase с расширением <code>.json</code>:",
            reply_markup=get_cancel_fsm_kb(),
        )
        return WAIT_FB_JSON

    if doc.file_size and doc.file_size > 512 * 1024:
        await safe_reply_text(
            update.message,
            f"{EMOJI['warn']} Файл слишком большой для JSON-ключа Firebase.",
            reply_markup=get_cancel_fsm_kb(),
        )
        return WAIT_FB_JSON

    try:
        tg_file = await doc.get_file()
        raw_bytes = bytes(await tg_file.download_as_bytearray())
        parsed = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(parsed, dict) or "private_key" not in parsed or "client_email" not in parsed:
            await safe_reply_text(
                update.message,
                f"{EMOJI['no_entry']} В JSON отсутствуют обязательные поля <code>client_email</code> и <code>private_key</code>.",
                reply_markup=get_cancel_fsm_kb(),
            )
            return WAIT_FB_JSON

        key_path = BASE_DIR / "firebase-service-account.json"
        key_path.write_bytes(raw_bytes)
        ok_init = firebase_manager.init_app(force_reload=True)
        if ok_init:
            firebase_manager.upload_db_to_cloud(force=True)
    except Exception as e:
        await safe_reply_text(
            update.message,
            f"{EMOJI['no_entry']} Ошибка чтения JSON-ключа: <code>{esc(str(e)[:200])}</code>",
            reply_markup=get_cancel_fsm_kb(),
        )
        return WAIT_FB_JSON

    context.user_data.clear()
    fb_text, fb_kb = build_firebase_manage_view()
    await safe_reply_text(
        update.message,
        f"{EMOJI['check']} <b>Ключ Firebase успешно обновлён!</b>\n\n" + fb_text,
        reply_markup=fb_kb,
    )
    return ConversationHandler.END


async def _execute_scrape_and_report(target_msg, channel_input: str, admin_user_id: int) -> int:
    slug = parse_public_channel_slug(channel_input)
    if not slug:
        await safe_reply_text(
            target_msg,
            f"{EMOJI['warn']} Не удалось распознать канал. Отправьте ссылку вида <code>https://t.me/loneasproofs</code> или <code>@channel</code>:",
            reply_markup=get_cancel_fsm_kb(),
        )
        return WAIT_SCRAPE_CHANNEL

    status_msg = await safe_reply_text(
        target_msg,
        f"{EMOJI['refresh']} <b>Выкачиваю данные из</b> <code>@{esc(slug)}</code>...\n"
        f"<i>Подключаюсь к каналу без добавления бота и собираю доказательства...</i>",
    )

    progress_state = {"pages": 0, "posts": 0, "records": 0}

    def _on_progress(pages: int, posts: int, records: int) -> None:
        progress_state["pages"] = pages
        progress_state["posts"] = posts
        progress_state["records"] = records

    task = asyncio.create_task(
        asyncio.to_thread(
            scrape_public_channel_sync,
            channel_input,
            admin_user_id,
            400,
            _on_progress,
        )
    )

    last_shown = (-1, -1)
    while not task.done():
        await asyncio.sleep(2.2)
        if task.done():
            break
        cur = (progress_state["pages"], progress_state["records"])
        if status_msg and cur != last_shown and progress_state["pages"] > 0:
            last_shown = cur
            try:
                await status_msg.edit_text(
                    f"{EMOJI['refresh']} <b>Выкачиваю данные из</b> <code>@{esc(slug)}</code>...\n\n"
                    + quote_block(
                        f"• <b>Загружено страниц:</b>  <code>{progress_state['pages']}</code>\n"
                        f"• <b>Обработано постов:</b>  <code>{progress_state['posts']}</code>\n"
                        f"• <b>Найдено записей:</b>  <code>{progress_state['records']}</code>"
                    )
                )
            except Exception:
                pass

    res = await task
    if not res.get("ok"):
        err_text = res.get("error", "Неизвестная ошибка")
        final_html = (
            f"{EMOJI['no_entry']} <b><u>Ошибка выкачки канала</u></b>\n\n"
            + quote_block(f"<i>{esc(err_text)}</i>")
        )
        if status_msg:
            try:
                await status_msg.edit_text(final_html, reply_markup=get_admin_panel_kb())
                return ConversationHandler.END
            except Exception:
                pass
        await safe_reply_text(target_msg, final_html, reply_markup=get_admin_panel_kb())
        return ConversationHandler.END

    fb_str = "Сохранено в Firebase" if res.get("firebase_saved") else "Сохранено локально в base.db"
    summary_html = (
        f"{EMOJI['check']} <b><u>ВЫКАЧКА ДАННЫХ ЗАВЕРШЕНА</u></b>\n\n"
        + quote_block(
            f"• <b>Канал:</b>  <code>@{esc(res['channel'])}</code>\n"
            f"• <b>Страниц просмотрено:</b>  <code>{res['pages_fetched']}</code>\n"
            f"• <b>Постов обработано:</b>  <code>{res['posts_parsed']}</code>\n"
            f"• <b>Добавлено новых скамеров:</b>  <code>{res['inserted']}</code>\n"
            f"• <b>Пропущено дублей:</b>  <code>{res['skipped']}</code>\n"
            f"• <b>Облако:</b>  <code>{fb_str}</code>"
        )
    )
    if status_msg:
        try:
            await status_msg.edit_text(summary_html, reply_markup=get_admin_panel_kb())
            return ConversationHandler.END
        except BadRequest as e:
            if "emoji" in str(e).lower() or "icon" in str(e).lower():
                await status_msg.edit_text(summary_html, reply_markup=rebuild_markup_without_icons(get_admin_panel_kb()))
                return ConversationHandler.END
        except Exception:
            pass
    await safe_reply_text(target_msg, summary_html, reply_markup=get_admin_panel_kb())
    return ConversationHandler.END


async def scrape_default_channel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query or not update.effective_user:
        return ConversationHandler.END
    if not is_full_admin(update.effective_user.id):
        await query.answer("Доступ разрешён только администраторам!", show_alert=True)
        return ConversationHandler.END
    await query.answer("Запускаю выкачку...")
    context.user_data.clear()
    return await _execute_scrape_and_report(query.message, INITIAL_SEED_CHANNEL, update.effective_user.id)


async def scrape_channel_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.effective_user:
        return WAIT_SCRAPE_CHANNEL
    if not is_full_admin(update.effective_user.id):
        return ConversationHandler.END
    raw = (update.message.text or "").strip()
    if not raw:
        await safe_reply_text(
            update.message,
            f"{EMOJI['warn']} Отправьте ссылку на канал (например, <code>https://t.me/loneasproofs</code>) или <code>@username</code>:",
            reply_markup=get_cancel_fsm_kb(),
        )
        return WAIT_SCRAPE_CHANNEL
    context.user_data.clear()
    return await _execute_scrape_and_report(update.message, raw, update.effective_user.id)


async def mod_add_target_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.effective_user:
        return WAIT_MOD_TARGET
    if not is_full_admin(update.effective_user.id):
        return ConversationHandler.END

    q_id, q_uname, fwd_name, val_err = extract_target_from_message(update.message)
    if val_err:
        await safe_reply_text(update.message, f"{EMOJI['no_entry']} {val_err}", reply_markup=get_cancel_fsm_kb())
        return WAIT_MOD_TARGET

    if not q_id and not q_uname:
        await safe_reply_text(
            update.message,
            f"{EMOJI['warn']} Некорректный ввод! Укажите <code>@username</code>, числовой <b>ID</b> или перешлите сообщение пользователя:",
            reply_markup=get_cancel_fsm_kb(),
        )
        return WAIT_MOD_TARGET

    is_valid, err_text, tg_id, tg_uname, _, tg_name, _ = await validate_and_resolve_user(
        context.bot, q_id, q_uname
    )
    if not is_valid or not (tg_id or q_id):
        await safe_reply_text(
            update.message,
            f"{EMOJI['no_entry']} {err_text or 'Не удалось определить числовой Telegram ID пользователя. Попросите пользователя написать /start боту или перешлите его сообщение.'}",
            reply_markup=get_cancel_fsm_kb(),
        )
        return WAIT_MOD_TARGET

    final_id = int(tg_id or q_id)
    final_uname = (tg_uname or q_uname or "").lstrip("@")
    final_name = tg_name or fwd_name or (f"@{final_uname}" if final_uname else f"ID {final_id}")

    if is_full_admin(final_id):
        context.user_data.clear()
        await safe_reply_text(
            update.message,
            f"{EMOJI['warn']} Пользователь <b>{esc(final_name)}</b> уже является главным администратором.",
            reply_markup=get_admin_panel_kb(),
        )
        return ConversationHandler.END

    db_add_moderator(final_id, final_uname, final_name, added_by=update.effective_user.id)
    context.user_data.clear()

    try:
        await safe_send_message(
            context.bot,
            chat_id=final_id,
            text=(
                f"{EMOJI['shield']} <b><u>Вам выдана роль модератора в {BOT_NAME}</u></b>\n\n"
                + quote_block(
                    "Теперь к вам будут приходить входящие заявки на добавление скамеров в базу.\n\n"
                    "<i>Доступные действия:</i> только <b>Принять</b> или <b>Отклонить</b> заявку."
                )
            ),
        )
    except Exception:
        pass

    mods_text, mods_kb = build_mods_manage_view()
    await safe_reply_text(
        update.message,
        f"{EMOJI['check']} <b>Модератор добавлен:</b>  <b>{esc(final_name)}</b> (<code>ID {final_id}</code>)\n\n"
        + mods_text,
        reply_markup=mods_kb,
    )
    return ConversationHandler.END


async def channel_set_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.effective_user:
        return WAIT_CHANNEL_SET
    if not is_full_admin(update.effective_user.id):
        return ConversationHandler.END

    msg = update.message
    target_chat = None

    fwd_origin = getattr(msg, "forward_origin", None)
    if fwd_origin and getattr(fwd_origin, "type", "") == "channel":
        target_chat = getattr(fwd_origin, "chat", None)
    if not target_chat:
        f_chat = getattr(msg, "forward_from_chat", None)
        if f_chat and getattr(f_chat, "type", "") == ChatType.CHANNEL:
            target_chat = f_chat

    if target_chat is not None:
        chan_ref: Any = target_chat.id
    else:
        raw = (msg.text or msg.caption or "").strip()
        m_tme = re.search(r"(?:https?://)?t\.me/@?([A-Za-z][A-Za-z0-9_]{2,34})", raw, re.IGNORECASE)
        if m_tme:
            chan_ref = "@" + m_tme.group(1)
        elif re.match(r"^-100\d{5,}$", raw):
            chan_ref = int(raw)
        elif re.match(r"^@[A-Za-z][A-Za-z0-9_]{2,34}$", raw):
            chan_ref = raw
        else:
            await safe_reply_text(
                msg,
                f"{EMOJI['warn']} Не удалось распознать канал.\n\n"
                + quote_block("Перешлите пост из нужного канала, либо отправьте <code>@username</code> или ID <code>-100...</code>:"),
                reply_markup=get_cancel_fsm_kb(),
            )
            return WAIT_CHANNEL_SET

    try:
        chat = await context.bot.get_chat(chan_ref)
        if chat.type != ChatType.CHANNEL:
            await safe_reply_text(
                msg,
                f"{EMOJI['no_entry']} Это не Telegram-канал! Укажите именно канал.",
                reply_markup=get_cancel_fsm_kb(),
            )
            return WAIT_CHANNEL_SET

        member = await context.bot.get_chat_member(chat.id, context.bot.id)
        status_str = str(getattr(member, "status", "")).lower()
        if status_str not in ("administrator", "creator"):
            await safe_reply_text(
                msg,
                f"{EMOJI['warn']} Бот не является администратором канала <b>{esc(chat.title or '')}</b>.\n"
                + quote_block("Выдайте боту права администратора в этом канале и отправьте канал ещё раз."),
                reply_markup=get_cancel_fsm_kb(),
            )
            return WAIT_CHANNEL_SET

        can_post = getattr(member, "can_post_messages", True)
        if can_post is False:
            await safe_reply_text(
                msg,
                f"{EMOJI['warn']} У бота в канале отключено право публикации сообщений (<code>can_post_messages</code>). Выдайте все разрешения и повторите.",
                reply_markup=get_cancel_fsm_kb(),
            )
            return WAIT_CHANNEL_SET

        db_set_proof_channel(chat.id, chat.username or "", chat.title or "")
    except Exception as e:
        await safe_reply_text(
            msg,
            f"{EMOJI['no_entry']} Не удалось подключить канал: <code>{esc(str(e))}</code>",
            reply_markup=get_cancel_fsm_kb(),
        )
        return WAIT_CHANNEL_SET

    context.user_data.clear()
    ch_text, ch_kb = build_channel_manage_view()
    await safe_reply_text(
        msg,
        f"{EMOJI['check']} <b>Канал пруфов успешно привязан!</b>\n\n" + ch_text,
        reply_markup=ch_kb,
    )
    return ConversationHandler.END


async def my_chat_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Автоматически фиксирует добавление/удаление бота в канале пруфов и группах."""
    cmu = getattr(update, "my_chat_member", None)
    if not cmu or not cmu.chat:
        return
    if getattr(cmu, "from_user", None):
        _cache_tg_user_obj(cmu.from_user)
    if getattr(cmu, "new_chat_member", None) and getattr(cmu.new_chat_member, "user", None):
        _cache_tg_user_obj(cmu.new_chat_member.user)
    chat = cmu.chat
    new_status = str(getattr(cmu.new_chat_member, "status", "")).lower()

    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        if new_status in ("member", "administrator", "creator"):
            _record_known_chat_id(chat.id)
        elif new_status in ("left", "kicked", "banned"):
            _record_known_chat_id(chat.id, remove=True)
        return

    if chat.type != ChatType.CHANNEL:
        return

    if new_status in ("administrator", "creator"):
        _record_known_chat_id(chat.id)
        can_post = getattr(cmu.new_chat_member, "can_post_messages", True)
        db_set_proof_channel(chat.id, chat.username or "", chat.title or "")
        warn_note = (
            ""
            if can_post is not False
            else f"\n\n{EMOJI['warn']} <i>Внимание: включите право «Публиковать сообщения» для корректной отправки пруфов!</i>"
        )
        title_safe = esc(chat.title or f"ID {chat.id}")
        addr_disp = f"<code>@{esc(chat.username)}</code>" if chat.username else f"<code>{chat.id}</code>"
        for adm_id in ADMIN_IDS:
            try:
                await safe_send_message(
                    context.bot,
                    chat_id=adm_id,
                    text=(
                        f"{EMOJI['check']} <b><u>Канал пруфов подключён автоматически!</u></b>\n\n"
                        + quote_block(
                            f"• <b>Канал:</b>  <b>{title_safe}</b>\n"
                            f"• <b>Адрес / ID:</b>  {addr_disp}\n\n"
                            f"<i>Принятые заявки с пруфами будут публиковаться сюда со ссылкой на пост.</i>"
                            + warn_note
                        )
                    ),
                )
            except Exception:
                pass
    elif new_status in ("left", "kicked", "banned", "member"):
        curr_id, _, _ = db_get_proof_channel()
        if curr_id == chat.id:
            db_set_proof_channel(None)
            for adm_id in ADMIN_IDS:
                try:
                    await safe_send_message(
                        context.bot,
                        chat_id=adm_id,
                        text=f"{EMOJI['warn']} Бот был удалён или разжалован из канала <b>{esc(chat.title or str(chat.id))}</b>. Привязка канала пруфов сброшена.",
                    )
                except Exception:
                    pass


async def fsm_cancel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer("Отменено")
        try:
            await safe_edit_text(
                query,
                f"{EMOJI['cross']} <b>Действие отменено.</b>",
                reply_markup=InlineKeyboardMarkup([
                    [make_btn("Главное меню", callback_data="main_home", emoji_key="gear")],
                ]),
            )
        except Exception:
            pass
    context.user_data.clear()
    return ConversationHandler.END


async def fsm_escape_to_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Позволяет пользователю выйти из незавершённого диалога при нажатии кнопок меню."""
    context.user_data.clear()
    await universal_callback_handler(update, context)
    return ConversationHandler.END


# =====================================================================
# ОБРАБОТЧИК ВСЕХ INLINE-КНОПОК (ПОЛЬЗОВАТЕЛЬСКИХ, МОДЕРАТОРСКИХ И АДМИНСКИХ)
# =====================================================================
async def universal_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user:
        return

    user = update.effective_user
    _cache_tg_user_obj(user)
    is_admin = is_full_admin(user.id)
    is_mod_or_admin = is_reviewer(user.id)
    data = query.data or ""

    # 0. Приветственное соглашение (доступно до принятия условий + перечитывание)
    if data == "accept_terms":
        db_accept_terms(user.id)
        await query.answer("Условия приняты! Добро пожаловать.")
        pending_arg = context.user_data.pop("_pending_start_arg", "")
        if query.message:
            try:
                await query.message.delete()
            except Exception:
                pass
            mode, dl_id, dl_uname = _parse_inline_start_arg(pending_arg)
            if mode == "chk" and (dl_id or dl_uname):
                await perform_scam_check_and_reply(
                    update,
                    context,
                    q_id=dl_id,
                    q_uname=dl_uname,
                    raw_query=str(dl_id or dl_uname),
                )
                return
            if mode == "rep" and (dl_id or dl_uname):
                t_key = build_target_key(dl_id, dl_uname)
                await safe_reply_text(
                    query.message,
                    f"{EMOJI['check']} <b>Условия приняты!</b>\n\n"
                    + quote_block("Нажмите кнопку ниже, чтобы продолжить подачу жалобы на выбранного пользователя:"),
                    reply_markup=InlineKeyboardMarkup([
                        [make_btn("Продолжить подачу жалобы", callback_data=f"report_prefill:{t_key}", style="danger", emoji_key="siren")],
                        [make_btn("Главное меню", callback_data="main_home", emoji_key="gear")],
                    ]),
                )
                return
            await send_main_menu_photo(query.message, user.id)
        return

    if data == "reread_terms":
        await query.answer()
        accepted = db_has_accepted_terms(user.id)
        await safe_edit_text(
            query,
            build_welcome_terms_text(full_mode=True),
            reply_markup=get_welcome_terms_kb(already_accepted=accepted, full_mode=True),
        )
        return

    if data == "reread_terms_short":
        await query.answer()
        accepted = db_has_accepted_terms(user.id)
        await safe_edit_text(
            query,
            build_welcome_terms_text(full_mode=False),
            reply_markup=get_welcome_terms_kb(already_accepted=accepted, full_mode=False),
        )
        return

    is_group_public_cb = bool(
        query.message
        and getattr(getattr(query.message, "chat", None), "type", None) != ChatType.PRIVATE
        and data.startswith(("scam_proofs:", "vote:", "no_proof:"))
    )
    if not db_has_accepted_terms(user.id) and not is_mod_or_admin and not is_group_public_cb:
        await query.answer("Сначала примите политику и условия пользования!", show_alert=True)
        if query.message and getattr(getattr(query.message, "chat", None), "type", None) == ChatType.PRIVATE:
            await send_welcome_terms_prompt(query.message, user.id, full_mode=False)
        return

    # 1. Профиль (проверить себя)
    if data == "my_profile":
        await query.answer("Проверяю ваш профиль...")
        full_name = " ".join(p for p in (user.first_name, user.last_name) if p).strip()
        db_upsert_user_cache(user_id=user.id, username=user.username or "", full_name=full_name)
        await perform_scam_check_and_reply(
            update,
            context,
            q_id=user.id,
            q_uname=(user.username or "").lower(),
            fwd_name=full_name,
            raw_query=str(user.id),
        )
        return

    # 2. Главное меню
    if data in ("main_home", "admin_home"):
        card_bio = await generate_main_menu_card_image()
        caption = build_main_home_text(user.id)
        kb = get_user_main_kb(user.id)

        if query.message and query.message.photo:
            try:
                await safe_edit_media_photo(query, photo=card_bio, caption=caption, reply_markup=kb)
            except Exception:
                card_bio.seek(0)
                await safe_reply_photo(query.message, photo=card_bio, caption=caption, reply_markup=kb)
        elif query.message:
            await safe_reply_photo(query.message, photo=card_bio, caption=caption, reply_markup=kb)
        await query.answer()
        return

    # 3. Искать пользователя (ввод текста/ID + кнопка «Выбрать пользователя» под строкой ввода)
    if data == "check_user_prompt":
        await query.answer("Отправьте данные или выберите пользователя ниже")
        is_priv = bool(update.effective_chat and update.effective_chat.type == ChatType.PRIVATE)
        if query.message:
            await send_search_user_prompt(query.message, context, is_private=is_priv)
        return

    # 4. Информация и ссылки - просто, чисто и аккуратно
    if data == "info_links":
        cards_quote = quote_block(
            f"• <b>Синяя карточка</b> - пользователь не найден в списках скамеров и гарантов <i>(доступна оценка репутации)</i>.\n"
            f"• <b>Красная карточка</b> - подтверждённый скамер с описанием нарушения и доказательствами.\n"
            f"• <b>Зелёная карточка</b> - официальный проверенный гарант."
        )
        text = (
            f"{EMOJI['eyes']} <b><u>ИНФОРМАЦИЯ И ССЫЛКИ - {BOT_NAME}</u></b>\n\n"
            + quote_block(
                f"• <b>Бот проверки:</b>  <code>{BOT_USERNAME}</code>\n"
                f"• <b>Прямая ссылка:</b>  <a href=\"{esc_attr(BOT_URL)}\">{BOT_URL}</a>"
            )
            + "\n\n<b>Как работает проверка:</b>\n"
            + f"<i>Отправьте боту</i> <code>@username</code>, <b>Telegram ID</b>, <i>перешлите сообщение или напишите прямо в любом чате</i> <code>{BOT_USERNAME} @username</code><i>.</i>\n\n"
            + "<b>Обозначения карточек:</b>\n"
            + f"{cards_quote}\n\n"
            + "<i>Если вы столкнулись с мошенником, нажмите «Подать жалобу на скамера» в главном меню и приложите доказательства.</i>"
        )
        kb = InlineKeyboardMarkup([
            [make_btn("Политика и условия", callback_data="reread_terms", emoji_key="lock")],
            [make_btn("Главное меню", callback_data="main_home", emoji_key="gear")],
        ])
        await safe_edit_text(query, text, reply_markup=kb)
        await query.answer()
        return

    # 5. Просмотр сохранённых медиа-пруфов по подтверждённому скамеру (отправка вместе альбомом)
    if data.startswith("scam_proofs:"):
        try:
            rec_id = int(data.split(":", 1)[1])
        except ValueError:
            await query.answer("Некорректный ID записи", show_alert=True)
            return
        row = db_get_scammer_by_id(rec_id)
        if not row:
            await query.answer("Запись не найдена", show_alert=True)
            return
        media_items = _parse_media_json(row["proof_media_json"] if "proof_media_json" in row.keys() else "[]")
        if not media_items:
            await query.answer("Медиа-пруфы к этой записи отсутствуют", show_alert=True)
            return
        await query.answer("Отправляю доказательства...")
        if query.message:
            s_id = row["user_id"]
            s_un = (row["username"] or "").strip().lstrip("@")
            s_ex = _parse_extra_usernames(row["extra_usernames"])
            s_name = row["full_name"] or (f"@{s_un}" if s_un else f"ID {s_id}")
            s_id_html = f"<code>{s_id}</code>" if s_id else "<i>Скрыт</i>"
            s_links = format_permanent_links_html(s_id, s_un, s_ex)
            cap = (
                f"{EMOJI['eyes']} <b>Доказательства по скамеру #{rec_id}</b> (<code>{len(media_items)}</code> файлов)\n\n"
                f"• <b>Профиль:</b> <b>{esc(clip_text(s_name, 56))}</b>\n"
                f"• <b>Юзернеймы:</b> {format_usernames_html(s_un, s_ex)}\n"
                f"• <b>Telegram ID:</b> {s_id_html}\n"
                f"• <b>Ссылки:</b> {s_links}\n"
                f"• <b>Ущерб:</b> <code>{esc(clip_text(row['damage'] or 'Не указан', 60))}</code>\n"
                f"• <b>Причина:</b> <i>{esc(clip_text(row['reason'] or 'Мошенничество', 160))}</i>"
            )
            await send_media_album_safe(context.bot, query.message.chat_id, media_items, caption_prefix=cap)
        return

    # 6. Голосование Лайк / Дизлайк (1 раз на 1 пользователя, работает и в ЛС, и в inline-чатах)
    if data.startswith("vote:"):
        parts = data.split(":", 2)
        if len(parts) != 3:
            await query.answer("Некорректные данные", show_alert=True)
            return

        vote_type, target_key = parts[1], parts[2]
        if vote_type not in ("like", "dislike"):
            await query.answer("Некорректный голос", show_alert=True)
            return

        ok, likes, dislikes = db_cast_vote_once(target_key, user.id, vote_type)
        if not ok:
            await query.answer(
                "Вы уже поставили оценку этому пользователю! Можно проголосовать только один раз.",
                show_alert=True,
            )
            return

        await query.answer("Лайк поставлен!" if vote_type == "like" else "Дизлайк поставлен!")

        raw_id = target_key[3:] if target_key.startswith("id:") else ""
        raw_un = target_key[3:] if target_key.startswith("un:") else ""
        q_uid = int(raw_id) if raw_id.isdigit() else None
        known_v = db_lookup_known_identity(user_id=q_uid, username=raw_un)
        eff_uid = q_uid or known_v["user_id"]
        eff_un = raw_un or known_v["username"]
        guar_match = db_find_guarantor(user_id=eff_uid, username=eff_un, extra_usernames=known_v["extra_usernames"])

        if query.message:
            if guar_match:
                new_kb = build_guarantor_kb(
                    guar_match["id"],
                    is_admin=is_admin,
                    target_key=target_key,
                    likes=likes,
                    dislikes=dislikes,
                )
            else:
                add_payload = f"{eff_uid or ''}|{(eff_un or '')[:24]}"
                new_kb = build_unverified_kb(target_key, likes, dislikes, add_payload, is_admin=is_admin)

            if query.message.caption is not None:
                old_caption = query.message.caption_html or query.message.caption
                rep_line = (
                    f"{EMOJI['fire']} <b>Репутация:</b>  "
                    f"{EMOJI['check']} <code>{likes}</code>  |  {EMOJI['cross']} <code>{dislikes}</code>"
                )
                new_caption = re.sub(
                    r".*<b>Репутация:</b>.*",
                    rep_line,
                    old_caption,
                    count=1,
                )
                try:
                    await query.edit_message_caption(caption=new_caption, reply_markup=new_kb)
                    return
                except BadRequest as e:
                    if "emoji" in str(e).lower() or "icon" in str(e).lower():
                        await query.edit_message_caption(
                            caption=new_caption,
                            reply_markup=rebuild_markup_without_icons(new_kb),
                        )
                        return
                except Exception:
                    pass

            await safe_edit_reply_markup(query, reply_markup=new_kb)
        elif query.inline_message_id:
            inline_kb = build_inline_result_kb(
                "guarantor" if guar_match else "unverified",
                target_key=target_key,
                user_id=eff_uid,
                username=eff_un,
                likes=likes,
                dislikes=dislikes,
            )
            try:
                await context.bot.edit_message_reply_markup(
                    inline_message_id=query.inline_message_id,
                    reply_markup=inline_kb,
                )
            except BadRequest as e:
                err_l = str(e).lower()
                if "emoji" in err_l or "icon" in err_l or "style" in err_l:
                    try:
                        await context.bot.edit_message_reply_markup(
                            inline_message_id=query.inline_message_id,
                            reply_markup=rebuild_markup_without_icons(inline_kb),
                        )
                    except Exception:
                        pass
            except Exception:
                pass
        return

    if data.startswith("no_proof:"):
        await query.answer("Ссылка на пруфы пока не добавлена.", show_alert=True)
        return

    # =================================================================
    # ЗАЯВКИ НА СКАМЕРОВ (ДОСТУПНО И МОДЕРАТОРАМ, И ГЛАВНЫМ АДМИНАМ)
    # =================================================================
    if data.startswith("rep_adm_accept:"):
        if not is_mod_or_admin:
            await query.answer("Доступ разрешён только модераторам и администраторам!", show_alert=True)
            return
        report_id = int(data.split(":", 1)[1])
        report = db_get_scam_report(report_id)
        if not report or report["status"] != "pending":
            await query.answer("Эта заявка уже рассмотрена!", show_alert=True)
            return

        await query.answer("Обрабатываю заявку...")
        prog_msg = await safe_send_message(
            context.bot,
            chat_id=user.id,
            text=f"{EMOJI['clock']} <i>Принимаю заявку #{report_id} и вношу запись в скам-базу...</i>",
        )

        try:
            old_msg_ids = json.loads(report["admin_msg_ids_json"] or "[]")
        except Exception:
            old_msg_ids = []
        await delete_previous_admin_report_messages(context.bot, report["assigned_admin_id"], old_msg_ids)

        db_finalize_report(report_id, status="accepted", admin_id=user.id)

        known_acc = db_lookup_known_identity(
            user_id=report["target_id"],
            username=report["target_username"] or "",
        )
        eff_tid = report["target_id"] or known_acc["user_id"]
        eff_tun = (report["target_username"] or known_acc["username"] or "").strip().lstrip("@").lower()
        eff_tname = report["target_name"] or known_acc["full_name"] or (f"@{eff_tun}" if eff_tun else f"ID {eff_tid}")
        if not eff_tid and eff_tun:
            try:
                _, _, mt_id, mt_un, mt_ex, mt_nm, _ = await asyncio.wait_for(
                    validate_and_resolve_user(context.bot, None, eff_tun, fetch_avatar=False),
                    timeout=3.5,
                )
                if mt_id:
                    eff_tid = mt_id
                if mt_un:
                    eff_tun = mt_un
                if mt_nm and _is_placeholder_name(eff_tname, eff_tun, eff_tid):
                    eff_tname = mt_nm
            except Exception:
                pass

        cached = db_get_user_cache(user_id=eff_tid, username=eff_tun)
        cached_extras = _merge_username_aliases(
            eff_tun,
            known_acc["extra_usernames"],
            _parse_extra_usernames(cached["extra_usernames"]) if cached and cached["extra_usernames"] else [],
        )
        media_items = _parse_media_json(report["media_json"])

        rec_id = db_add_or_update_scammer(
            user_id=eff_tid,
            username=eff_tun,
            full_name=eff_tname,
            reason=report["description"],
            proof=f"Подтверждено по жалобе #{report_id} ({len(media_items)} медиа)" if media_items else f"Подтверждено по жалобе #{report_id}",
            damage="По жалобе",
            added_by=user.id,
            extra_usernames=cached_extras,
            proof_media_json=report["media_json"] or "[]",
        )

        if prog_msg:
            await animate_status_steps(
                prog_msg,
                [f"{EMOJI['eyes']} <i>Публикую доказательства в канал и формирую ссылку...</i>"],
                delay=0.22,
            )

        report_for_pub = {
            "target_id": eff_tid,
            "target_username": eff_tun,
            "target_name": eff_tname,
            "description": report["description"],
            "media_json": report["media_json"],
        }
        # Публикуем пруфы в настроенный канал и копируем ссылку на сообщение
        channel_post_url = await publish_report_proofs_to_channel(
            context.bot,
            report_id=report_id,
            report=report_for_pub,
            rec_id=rec_id,
            extra_usernames=cached_extras,
        )
        if channel_post_url:
            db_add_or_update_scammer(
                user_id=eff_tid,
                username=eff_tun,
                full_name=eff_tname,
                reason=report["description"],
                proof=channel_post_url,
                damage="По жалобе",
                added_by=user.id,
                extra_usernames=cached_extras,
                proof_url=channel_post_url,
                proof_media_json=report["media_json"] or "[]",
            )

        rep_proof_note = (
            f"\n{EMOJI['eyes']} <b>Пост с пруфами:</b> <a href=\"{esc_attr(channel_post_url)}\">Открыть в канале</a>"
            if channel_post_url
            else ""
        )
        try:
            await safe_send_message(
                context.bot,
                chat_id=int(report["reporter_id"]),
                text=(
                    f"{EMOJI['check']} <b><u>Ваша жалоба #{report_id} принята!</u></b>\n\n"
                    + quote_block(
                        f"{EMOJI['siren']} Пользователь <b>{esc(report['target_name'])}</b> занесён в скам-базу "
                        f"под номером <b>#{rec_id}</b>.{rep_proof_note}\n\n"
                        f"<i>Спасибо за помощь в защите сообщества!</i>"
                    )
                ),
            )
        except Exception:
            pass

        if prog_msg:
            try:
                await prog_msg.delete()
            except Exception:
                pass

        adm_proof_note = (
            f"\n{EMOJI['eyes']} <b>Ссылка на пост с пруфами:</b>\n<code>{esc(channel_post_url)}</code>"
            if channel_post_url
            else ""
        )
        confirm_kb = (
            get_admin_panel_kb()
            if is_admin
            else InlineKeyboardMarkup([[make_btn("Главное меню", callback_data="main_home", emoji_key="gear")]])
        )
        await safe_send_message(
            context.bot,
            chat_id=user.id,
            text=(
                f"{EMOJI['check']} <b><u>Заявка #{report_id} принята!</u></b>\n\n"
                + quote_block(
                    f"Нарушитель <b>{esc(report['target_name'])}</b> добавлен в скам-базу "
                    f"(запись <code>#{rec_id}</code>).{adm_proof_note}"
                )
            ),
            reply_markup=confirm_kb,
        )
        return

    if data.startswith("rep_adm_reject:"):
        if not is_mod_or_admin:
            await query.answer("Доступ разрешён только модераторам и администраторам!", show_alert=True)
            return
        report_id = int(data.split(":", 1)[1])
        report = db_get_scam_report(report_id)
        if not report or report["status"] != "pending":
            await query.answer("Эта заявка уже рассмотрена!", show_alert=True)
            return

        try:
            old_msg_ids = json.loads(report["admin_msg_ids_json"] or "[]")
        except Exception:
            old_msg_ids = []
        await delete_previous_admin_report_messages(context.bot, report["assigned_admin_id"], old_msg_ids)

        db_finalize_report(report_id, status="rejected", admin_id=user.id, reject_reason="")

        try:
            await safe_send_message(
                context.bot,
                chat_id=int(report["reporter_id"]),
                text=(
                    f"{EMOJI['cross']} <b><u>Ваша жалоба #{report_id} отклонена</u></b>\n\n"
                    + quote_block("<i>Если у вас появятся дополнительные доказательства, вы можете подать заявку повторно.</i>")
                ),
            )
        except Exception:
            pass

        await query.answer("Заявка отклонена!")
        confirm_kb = (
            get_admin_panel_kb()
            if is_admin
            else InlineKeyboardMarkup([[make_btn("Главное меню", callback_data="main_home", emoji_key="gear")]])
        )
        await safe_send_message(
            context.bot,
            chat_id=user.id,
            text=f"{EMOJI['cross']} Заявка <b>#{report_id}</b> отклонена.",
            reply_markup=confirm_kb,
        )
        return

    # =================================================================
    # ДАЛЕЕ - ТОЛЬКО ДЛЯ ГЛАВНЫХ АДМИНИСТРАТОРОВ (ПОЛНЫЕ ПРАВА)
    # =================================================================
    if not is_admin:
        await query.answer("Этот раздел доступен только главным администраторам!", show_alert=True)
        return

    if data == "admin_panel":
        stats = db_get_stats()
        chan_id, chan_uname, chan_title = db_get_proof_channel()
        chan_disp = f"@{chan_uname}" if chan_uname else (chan_title or f"ID {chan_id}" if chan_id else "Не привязан")
        mt_ok, mt_msg = _is_mtproto_ready()
        mt_disp = f"Включён ({mt_msg})" if mt_ok else f"Не настроен ({mt_msg}) • /set_api"
        text = (
            f"{EMOJI['gear']} <b><u>АДМИН-ПАНЕЛЬ • {BOT_NAME}</u></b>\n\n"
            + quote_block(
                f"{EMOJI['crown']} <b>Зашли в бота (/start):</b>  <code>{stats['total_started']}</code>\n"
                f"{EMOJI['siren']} <b>Скамеров в базе:</b>  <code>{stats['total_scammers']}</code>\n"
                f"{EMOJI['shield']} <b>Гарантов в базе:</b>  <code>{stats['total_guarantors']}</code>\n"
                f"{EMOJI['shield']} <b>Модераторов заявок:</b>  <code>{stats['total_mods']}</code>\n"
                f"{EMOJI['clock']} <b>Активных жалоб в очереди:</b>  <code>{stats['pending_reports']}</code>\n"
                f"{EMOJI['eyes']} <b>Канал пруфов:</b>  <code>{esc(chan_disp)}</code>\n"
                f"{EMOJI['lock']} <b>Определитель ID (MTProto):</b>  <code>{esc(mt_disp)}</code>\n"
                f"{EMOJI['search']} <b>Всего проверок 24/7:</b>  <code>{stats['total_checks']}</code>"
            )
            + "\n\n<i>Выберите действие для управления базой:</i>"
        )
        await safe_edit_text(query, text, reply_markup=get_admin_panel_kb())
        await query.answer()
        return

    if data == "adm_firebase":
        fb_text, fb_kb = build_firebase_manage_view()
        await safe_edit_text(query, fb_text, reply_markup=fb_kb)
        await query.answer()
        return

    if data == "adm_fb_sync":
        await query.answer("Выгружаю base.db в Firebase...")
        if query.message:
            await animate_status_steps(
                query.message,
                [f"{EMOJI['refresh']} <i>Сжимаю и сохраняю base.db в Firestore ({esc(firebase_manager.collection_name)})...</i>"],
                delay=0.25,
            )
        ok = firebase_manager.upload_db_to_cloud(force=True)
        fb_text, fb_kb = build_firebase_manage_view()
        banner = (
            f"{EMOJI['check']} <b>Синхронизация завершена успешно!</b>\n\n"
            if ok
            else f"{EMOJI['warn']} <b>Не удалось выгрузить базу:</b> <i>{esc(firebase_manager.last_sync_status)}</i>\n\n"
        )
        await safe_edit_text(query, banner + fb_text, reply_markup=fb_kb)
        return

    if data == "adm_fb_restore":
        await query.answer("Загружаю base.db из Firebase...")
        if query.message:
            await animate_status_steps(
                query.message,
                [f"{EMOJI['refresh']} <i>Скачиваю и проверяю base.db из Firestore ({esc(firebase_manager.collection_name)})...</i>"],
                delay=0.25,
            )
        ok = firebase_manager.download_db_on_startup()
        if ok:
            init_db()
        fb_text, fb_kb = build_firebase_manage_view()
        banner = (
            f"{EMOJI['check']} <b>База base.db восстановлена из Firebase!</b>\n\n"
            if ok
            else f"{EMOJI['warn']} <b>Восстановление не выполнено:</b> <i>{esc(firebase_manager.last_sync_status)}</i>\n\n"
        )
        await safe_edit_text(query, banner + fb_text, reply_markup=fb_kb)
        return

    if data == "adm_mods":
        mods_text, mods_kb = build_mods_manage_view()
        await safe_edit_text(query, mods_text, reply_markup=mods_kb)
        await query.answer()
        return

    if data.startswith("adm_mod_del:"):
        try:
            mod_uid = int(data.split(":", 1)[1])
        except ValueError:
            await query.answer("Некорректный ID", show_alert=True)
            return
        removed = db_remove_moderator(mod_uid)
        await query.answer("Модератор снят!" if removed else "Уже снят")
        if removed:
            try:
                await safe_send_message(
                    context.bot,
                    chat_id=mod_uid,
                    text=f"{EMOJI['warn']} Ваша роль модератора заявок в <b>{BOT_NAME}</b> была снята администратором.",
                )
            except Exception:
                pass
        mods_text, mods_kb = build_mods_manage_view()
        await safe_edit_text(query, mods_text, reply_markup=mods_kb)
        return

    if data == "adm_channel":
        ch_text, ch_kb = build_channel_manage_view()
        await safe_edit_text(query, ch_text, reply_markup=ch_kb)
        await query.answer()
        return

    if data == "adm_channel_clear":
        db_set_proof_channel(None)
        await query.answer("Канал пруфов отвязан")
        ch_text, ch_kb = build_channel_manage_view()
        await safe_edit_text(query, ch_text, reply_markup=ch_kb)
        return

    if data == "admin_stats":
        stats = db_get_stats()
        now_str = datetime.now().strftime("%H:%M:%S")
        mt_ok, mt_msg = _is_mtproto_ready()
        mt_disp = f"Активен ({mt_msg})" if mt_ok else f"Не настроен ({mt_msg})"
        text = (
            f"{EMOJI['chart']} <b><u>Статистика {BOT_NAME}</u></b>\n\n"
            + quote_block(
                f"{EMOJI['crown']} <b>Зашли в бота (/start):</b>  <code>{stats['total_started']}</code>\n"
                f"{EMOJI['check']} <b>Приняли правила:</b>  <code>{stats['total_agreed']}</code>\n"
                f"{EMOJI['search']} <b>Всего проверок 24/7:</b>  <code>{stats['total_checks']}</code>\n"
                f"{EMOJI['no_entry']} <b>Выявлено скамеров:</b>  <code>{stats['scammer_hits']}</code>\n"
                f"{EMOJI['siren']} <b>Скамеров в базе:</b>  <code>{stats['total_scammers']}</code>\n"
                f"{EMOJI['shield']} <b>Гарантов в базе:</b>  <code>{stats['total_guarantors']}</code>\n"
                f"{EMOJI['shield']} <b>Модераторов заявок:</b>  <code>{stats['total_mods']}</code>\n"
                f"{EMOJI['clock']} <b>Активных жалоб:</b>  <code>{stats['pending_reports']}</code>\n"
                f"{EMOJI['fire']} <b>Оценок поставлено:</b>  <code>{stats['total_votes']}</code>\n"
                f"{EMOJI['lock']} <b>MTProto ID:</b>  <code>{esc(mt_disp)}</code>\n"
                f"{EMOJI['clock']} <b>Аптайм:</b>  <code>{get_uptime()}</code>"
            )
            + f"\n\n<i>Обновлено в</i> <code>{now_str}</code>"
        )
        kb = InlineKeyboardMarkup([
            [make_btn("Обновить", callback_data="admin_stats", emoji_key="refresh")],
            [make_btn("Админ-панель", callback_data="admin_panel", emoji_key="gear")],
        ])
        await safe_edit_text(query, text, reply_markup=kb)
        await query.answer()
        return

    if data.startswith("scam_list:"):
        try:
            page = int(data.split(":", 1)[1])
        except ValueError:
            page = 1
        rows, total_pages, total = db_get_scammers_page(page=page, page_size=6)
        if not rows:
            text = (
                f"{EMOJI['check']} <b><u>Скам-база пока пуста</u></b>\n\n"
                + quote_block("<i>Нажмите «Занести скамера», чтобы внести первую запись.</i>")
            )
            kb = InlineKeyboardMarkup([
                [make_btn("Занести скамера", callback_data="scam_add_start", style="danger", emoji_key="plus")],
                [make_btn("Админ-панель", callback_data="admin_panel", emoji_key="gear")],
            ])
        else:
            list_items = []
            btn_rows = []
            for r in rows:
                tag = f"@{r['username']}" if r["username"] else f"ID {r['user_id']}"
                name_short = (r["full_name"] or tag)[:22]
                list_items.append(
                    f"• <b>#{r['id']}</b> - <b>{esc(name_short)}</b> (<code>{esc(tag)}</code>) • <i>{esc(clip_text(r['damage'] or 'Скам', 28))}</i>"
                )
                btn_rows.append([
                    make_btn(f"#{r['id']} • {name_short} ({tag})", callback_data=f"scam_view:{r['id']}", emoji_key="siren")
                ])

            nav_btns = []
            if page > 1:
                nav_btns.append(make_btn("Назад", callback_data=f"scam_list:{page - 1}", emoji_key="search"))
            if page < total_pages:
                nav_btns.append(make_btn("Вперёд", callback_data=f"scam_list:{page + 1}", emoji_key="search"))
            if nav_btns:
                btn_rows.append(nav_btns)

            btn_rows.append([make_btn("Админ-панель", callback_data="admin_panel", emoji_key="gear")])
            text = (
                f"{EMOJI['siren']} <b><u>СПИСОК СКАМЕРОВ</u></b>  •  <code>Всего: {total}</code>\n"
                f"<i>Страница {page} из {total_pages}</i>\n\n"
                + quote_block("\n".join(list_items))
            )
            kb = InlineKeyboardMarkup(btn_rows)

        await safe_edit_text(query, text, reply_markup=kb)
        await query.answer()
        return

    if data.startswith("guar_list:"):
        try:
            page = int(data.split(":", 1)[1])
        except ValueError:
            page = 1
        rows, total_pages, total = db_get_guarantors_page(page=page, page_size=6)
        if not rows:
            text = (
                f"{EMOJI['crown']} <b><u>База гарантов пока пуста</u></b>\n\n"
                + quote_block("<i>Нажмите «Добавить гаранта», чтобы внести проверенного человека.</i>")
            )
            kb = InlineKeyboardMarkup([
                [make_btn("Добавить гаранта", callback_data="guar_add_start", style="success", emoji_key="shield")],
                [make_btn("Админ-панель", callback_data="admin_panel", emoji_key="gear")],
            ])
        else:
            list_items = []
            btn_rows = []
            for r in rows:
                tag = f"@{r['username']}" if r["username"] else f"ID {r['user_id']}"
                name_short = (r["full_name"] or tag)[:22]
                list_items.append(
                    f"• <b>#{r['id']}</b> - <b>{esc(name_short)}</b> (<code>{esc(tag)}</code>)"
                )
                btn_rows.append([
                    make_btn(f"#{r['id']} • {name_short} ({tag})", callback_data=f"guar_view:{r['id']}", emoji_key="crown")
                ])

            nav_btns = []
            if page > 1:
                nav_btns.append(make_btn("Назад", callback_data=f"guar_list:{page - 1}", emoji_key="search"))
            if page < total_pages:
                nav_btns.append(make_btn("Вперёд", callback_data=f"guar_list:{page + 1}", emoji_key="search"))
            if nav_btns:
                btn_rows.append(nav_btns)

            btn_rows.append([make_btn("Админ-панель", callback_data="admin_panel", emoji_key="gear")])
            text = (
                f"{EMOJI['crown']} <b><u>СПИСОК ГАРАНТОВ</u></b>  •  <code>Всего: {total}</code>\n"
                f"<i>Страница {page} из {total_pages}</i>\n\n"
                + quote_block("\n".join(list_items))
            )
            kb = InlineKeyboardMarkup(btn_rows)

        await safe_edit_text(query, text, reply_markup=kb)
        await query.answer()
        return

    if data.startswith("scam_view:"):
        rec_id = int(data.split(":", 1)[1])
        row = db_get_scammer_by_id(rec_id)
        if not row:
            await query.answer("Запись не найдена!", show_alert=True)
            return

        await query.answer("Загружаю карточку...")
        _, _, tg_id, tg_uname, tg_extras, tg_name, avatar_bytes = await validate_and_resolve_user(
            context.bot, row["user_id"], row["username"]
        )
        final_id = tg_id or row["user_id"]
        final_uname = tg_uname or row["username"]
        row_old_un = (row["username"] or "").strip().lstrip("@").lower()
        merged_extras = _merge_username_aliases(
            final_uname,
            tg_extras,
            _parse_extra_usernames(row["extra_usernames"]),
            row_old_un if row_old_un and row_old_un != (final_uname or "").lower() else "",
        )
        final_name = tg_name or row["full_name"] or (f"@{final_uname}" if final_uname else f"ID {final_id}")

        card_bio = await generate_scammer_card_image(
            target_user_id=final_id,
            username=final_uname,
            full_name=final_name,
            reason=row["reason"],
            damage=row["damage"],
            added_at=row["added_at"],
            case_id=row["id"],
            avatar_bytes=avatar_bytes,
        )
        proof_url = (row["proof_url"] or "").strip()
        media_cnt = len(_parse_media_json(row["proof_media_json"] if "proof_media_json" in row.keys() else "[]"))
        caption = build_scammer_caption(row, final_name, final_uname, merged_extras, final_id, is_dossier=True)
        await safe_reply_photo(
            query.message,
            photo=card_bio,
            caption=caption,
            reply_markup=build_scammer_kb(row["id"], proof_url=proof_url, is_admin=True, proof_media_count=media_cnt),
        )
        return

    if data.startswith("guar_view:"):
        rec_id = int(data.split(":", 1)[1])
        row = db_get_guarantor_by_id(rec_id)
        if not row:
            await query.answer("Запись не найдена!", show_alert=True)
            return

        await query.answer("Загружаю карточку...")
        _, _, tg_id, tg_uname, tg_extras, tg_name, avatar_bytes = await validate_and_resolve_user(
            context.bot, row["user_id"], row["username"]
        )
        final_id = tg_id or row["user_id"]
        final_uname = tg_uname or row["username"]
        row_old_un = (row["username"] or "").strip().lstrip("@").lower()
        merged_extras = _merge_username_aliases(
            final_uname,
            tg_extras,
            _parse_extra_usernames(row["extra_usernames"]),
            row_old_un if row_old_un and row_old_un != (final_uname or "").lower() else "",
        )
        final_name = tg_name or row["full_name"] or (f"@{final_uname}" if final_uname else f"ID {final_id}")

        card_bio = await generate_guarantor_card_image(
            target_user_id=final_id,
            username=final_uname,
            full_name=final_name,
            note=row["note"],
            added_at=row["added_at"],
            guar_id=row["id"],
            avatar_bytes=avatar_bytes,
        )
        target_key = build_target_key(final_id, final_uname)
        likes, dislikes = db_get_votes(target_key)
        caption = build_guarantor_caption(
            row,
            final_name,
            final_uname,
            merged_extras,
            final_id,
            is_dossier=True,
            likes=likes,
            dislikes=dislikes,
        )
        await safe_reply_photo(
            query.message,
            photo=card_bio,
            caption=caption,
            reply_markup=build_guarantor_kb(
                row["id"],
                is_admin=True,
                target_key=target_key,
                likes=likes,
                dislikes=dislikes,
            ),
        )
        return

    if data.startswith("scam_del_ask:"):
        rec_id = int(data.split(":", 1)[1])
        kb = InlineKeyboardMarkup([
            [
                make_btn("Да, удалить", callback_data=f"scam_del_confirm:{rec_id}", style="danger", emoji_key="check"),
                make_btn("Отмена", callback_data="scam_list:1", emoji_key="cross"),
            ]
        ])
        await safe_reply_text(
            query.message,
            f"{EMOJI['warn']} <b>Подтверждение удаления</b>\n\n"
            + quote_block(f"Вы уверены, что хотите удалить скамера <code>#{rec_id}</code> из базы?"),
            reply_markup=kb,
        )
        await query.answer()
        return

    if data.startswith("scam_del_confirm:"):
        rec_id = int(data.split(":", 1)[1])
        ok = db_delete_scammer(rec_id)
        await query.answer("Удалено" if ok else "Уже удалено")
        await safe_edit_text(
            query,
            f"{EMOJI['trash']} Запись скамера <code>#{rec_id}</code> успешно удалена из базы.",
            reply_markup=InlineKeyboardMarkup([
                [make_btn("Админ-панель", callback_data="admin_panel", emoji_key="gear")],
            ]),
        )
        return

    if data.startswith("guar_del_ask:"):
        rec_id = int(data.split(":", 1)[1])
        kb = InlineKeyboardMarkup([
            [
                make_btn("Да, удалить", callback_data=f"guar_del_confirm:{rec_id}", style="danger", emoji_key="check"),
                make_btn("Отмена", callback_data="guar_list:1", emoji_key="cross"),
            ]
        ])
        await safe_reply_text(
            query.message,
            f"{EMOJI['warn']} <b>Подтверждение удаления</b>\n\n"
            + quote_block(f"Вы уверены, что хотите удалить гаранта <code>#{rec_id}</code> из базы?"),
            reply_markup=kb,
        )
        await query.answer()
        return

    if data.startswith("guar_del_confirm:"):
        rec_id = int(data.split(":", 1)[1])
        ok = db_delete_guarantor(rec_id)
        await query.answer("Удалено" if ok else "Уже удалено")
        await safe_edit_text(
            query,
            f"{EMOJI['trash']} Запись гаранта <code>#{rec_id}</code> успешно удалена из базы.",
            reply_markup=InlineKeyboardMarkup([
                [make_btn("Админ-панель", callback_data="admin_panel", emoji_key="gear")],
            ]),
        )
        return


# =====================================================================
# ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОШИБОК И ИНИЦИАЛИЗАЦИЯ ПРИЛОЖЕНИЯ
# =====================================================================
async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error
    if isinstance(err, Forbidden):
        logger.warning("Доступ запрещён (пользователь заблокировал бота): %s", err)
        return
    if isinstance(err, RetryAfter):
        logger.warning("Превышен лимит Telegram API, пауза %s сек", getattr(err, "retry_after", 1))
        return
    if isinstance(err, (TimedOut, NetworkError)):
        logger.warning("Временная сетевая ошибка Telegram: %s", err)
        return
    if isinstance(err, BadRequest):
        err_l = str(err).lower()
        if "message is not modified" in err_l or "query is too old" in err_l:
            return
        logger.warning("Telegram BadRequest: %s", err)
        return
    logger.exception("Необработанная ошибка при обработке обновления %s:", update, exc_info=err)


async def post_init_setup(application: Application) -> None:
    global _FALLBACK_ROTATION_TASK
    try:
        await application.bot.set_my_commands([
            BotCommand("start", "🛡 Главное меню"),
            BotCommand("menu", "📋 Открыть меню"),
            BotCommand("check", "🔍 Искать пользователя"),
            BotCommand("profile", "👑 Проверить свой профиль"),
            BotCommand("report", "🚨 Подать жалобу на скамера"),
        ])
    except Exception as e:
        logger.debug("Не удалось установить команды бота: %s", e)

    if application.job_queue:
        application.job_queue.run_repeating(rotate_stale_reports_job, interval=60, first=30)
    else:
        _FALLBACK_ROTATION_TASK = asyncio.create_task(_fallback_rotation_loop(application.bot))

    asyncio.create_task(_initial_seed_loneasproofs_task())


async def post_shutdown_cleanup(application: Application) -> None:
    global _FALLBACK_ROTATION_TASK
    if _FALLBACK_ROTATION_TASK and not _FALLBACK_ROTATION_TASK.done():
        _FALLBACK_ROTATION_TASK.cancel()
        try:
            await _FALLBACK_ROTATION_TASK
        except asyncio.CancelledError:
            pass
    try:
        firebase_manager.stop()
    except Exception:
        pass


def main() -> None:
    migrate_legacy_db_if_needed()
    firebase_manager.download_db_on_startup()
    init_db()
    if firebase_manager._cloud_doc_missing:
        firebase_manager.upload_db_to_cloud(force=True)
    firebase_manager.start_periodic_sync(interval_seconds=60)

    defaults = Defaults(parse_mode=ParseMode.HTML)
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .defaults(defaults)
        .post_init(post_init_setup)
        .post_shutdown(post_shutdown_cleanup)
        .build()
    )

    admin_filter = filters.User(user_id=ADMIN_IDS)

    # 1. Единый ConversationHandler для жалоб пользователей и админских действий
    main_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(report_start_cb, pattern=r"^report_start$"),
            CallbackQueryHandler(report_prefill_cb, pattern=r"^report_prefill:"),
            CommandHandler("report", report_start_command),
            CommandHandler("start", start_or_menu_handler),
            CallbackQueryHandler(
                fsm_start_cb,
                pattern=r"^(scam_add_start|guar_add_start|adm_mod_add|adm_channel_set|adm_fb_upload|adm_scrape_start|scam_quick_add:.*|guar_quick_add:.*|rep_adm_reject_reason:.*)$",
            ),
        ],
        states={
            # Подача жалобы пользователем
            REP_WAIT_TARGET: [
                MessageHandler(filters.ALL & ~filters.COMMAND, rep_target_step),
            ],
            REP_WAIT_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, rep_desc_step),
            ],
            REP_WAIT_MEDIA: [
                CallbackQueryHandler(rep_preview_actions_cb, pattern=r"^rep_media_done$"),
                MessageHandler(filters.ALL & ~filters.COMMAND, rep_media_collect_step),
            ],
            REP_PREVIEW: [
                CallbackQueryHandler(
                    rep_preview_actions_cb,
                    pattern=r"^(rep_submit|rep_edit_target|rep_edit_desc|rep_edit_media)$",
                ),
            ],
            REP_EDIT_TARGET: [
                MessageHandler(filters.ALL & ~filters.COMMAND, rep_edit_target_step),
            ],
            REP_EDIT_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, rep_edit_desc_step),
            ],
            # Отклонение жалобы с причиной (админ или модератор)
            ADM_REJECT_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_reject_reason_step),
            ],
            # Админское добавление скамера / гаранта / модератора / канала / Firebase JSON
            WAIT_SCAM_TARGET: [
                MessageHandler(admin_filter & filters.ALL & ~filters.COMMAND, scam_add_target_step),
            ],
            WAIT_SCAM_REASON: [
                MessageHandler(admin_filter & filters.TEXT & ~filters.COMMAND, scam_add_reason_step),
            ],
            WAIT_SCAM_DAMAGE: [
                MessageHandler(admin_filter & filters.TEXT & ~filters.COMMAND, scam_add_damage_step),
            ],
            WAIT_SCAM_PROOF: [
                MessageHandler(admin_filter & filters.TEXT & ~filters.COMMAND, scam_add_proof_step),
            ],
            WAIT_GUAR_TARGET: [
                MessageHandler(admin_filter & filters.ALL & ~filters.COMMAND, guar_add_target_step),
            ],
            WAIT_GUAR_NOTE: [
                MessageHandler(admin_filter & filters.TEXT & ~filters.COMMAND, guar_add_note_step),
            ],
            WAIT_MOD_TARGET: [
                MessageHandler(admin_filter & filters.ALL & ~filters.COMMAND, mod_add_target_step),
            ],
            WAIT_CHANNEL_SET: [
                MessageHandler(admin_filter & filters.ALL & ~filters.COMMAND, channel_set_step),
            ],
            WAIT_FB_JSON: [
                MessageHandler(admin_filter & filters.ALL & ~filters.COMMAND, firebase_json_upload_step),
            ],
            WAIT_SCRAPE_CHANNEL: [
                CallbackQueryHandler(scrape_default_channel_cb, pattern=r"^adm_scrape_default$"),
                MessageHandler(admin_filter & filters.TEXT & ~filters.COMMAND, scrape_channel_step),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(fsm_cancel_cb, pattern=r"^fsm_cancel$"),
            CallbackQueryHandler(
                fsm_escape_to_menu_cb,
                pattern=r"^(main_home|admin_home|my_profile|check_user_prompt|info_links|admin_panel|adm_mods|adm_channel|adm_firebase|adm_fb_sync|adm_fb_restore|accept_terms|reread_terms|reread_terms_short)$",
            ),
            CommandHandler(["start", "menu", "cancel"], start_or_menu_handler),
            CommandHandler("check", check_command_handler),
        ],
        allow_reentry=True,
    )
    application.add_handler(main_conv)

    # 2. Inline-режим в любом чате (@KrakazeBaseApp @username / ID)
    application.add_handler(InlineQueryHandler(inline_query_handler))

    # 3. Автоматическое определение канала пруфов при выдаче админки боту
    application.add_handler(ChatMemberHandler(my_chat_member_handler, ChatMemberHandler.MY_CHAT_MEMBER))

    # 4. Команды /start, /menu, /check, /profile и админская настройка MTProto /set_api
    application.add_handler(CommandHandler(["start", "menu"], start_or_menu_handler))
    application.add_handler(CommandHandler("check", check_command_handler))
    application.add_handler(CommandHandler(["profile", "me"], profile_command_handler))
    application.add_handler(CommandHandler("set_api", set_api_command_handler))

    # 5. Все inline-кнопки меню, профилей, жалоб и админ-панели
    application.add_handler(CallbackQueryHandler(universal_callback_handler))

    # 6. Проверка любого @username, ID, ссылки, контакта или пересланного сообщения 24/7
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, free_text_check_handler))

    # 7. Глобальный обработчик ошибок
    application.add_error_handler(global_error_handler)

    logger.info(
        "%s (%s) запущен 24/7! База: %s | Firestore: %s/%s | ADMIN_IDS: %s",
        BOT_NAME,
        BOT_USERNAME,
        DB_PATH.name,
        firebase_manager.collection_name,
        firebase_manager.doc_name,
        ADMIN_IDS,
    )
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
