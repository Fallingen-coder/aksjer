"""Supabase-klient."""

import os
from supabase import create_client, Client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]


def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)
