import os
import re
from typing import Optional, Literal
from fastapi import FastAPI, Query
from pydantic import BaseModel

try:
    from openai import OpenAI
except Exception:  # OpenAI opcional
    OpenAI = None

APP_NAME = os.getenv("APP_NAME", "FerroAI Cloud")

app = FastAPI(title=APP_NAME)

class IntentResponse(BaseModel):
    action: Literal[
        "say", "call", "whatsapp", "emails_read", "unknown"
    ] = "unknown"
    say: Optional[str] = None
    call_number: Optional[str] = None
    call_contact: Optional[str] = None
    whatsapp_contact: Optional[str] = None
    whatsapp_message: Optional[str] = None
    emails: Optional[list[str]] = None

@app.get("/health")
def health():
    return {"status": "ok", "app": APP_NAME}

# ---------- Reglas básicas ----------
CALL_RE = re.compile(r"(?i)llama(r)? a (?P<contacto>.+)$")
WA_RE = re.compile(r"(?i)(whatsapp|wasap|manda|envía|enviar) (a )?(?P<contacto>[^:]+): (?P<msg>.+)$")
READ_MAIL_RE = re.compile(r"(?i)(léeme|lee|leer)( mis)? (correos|emails|gmail)")
SALUDO_RE = re.compile(r"(?i)hola|buenos dias|buenas tardes|buenas noches")

CALL_EN_RE = re.compile(r"(?i)call (?P<contact>.+)$")
WA_EN_RE = re.compile(r"(?i)(send|whatsapp) to (?P<contact>[^:]+): (?P<msg>.+)$")
READ_MAIL_EN_RE = re.compile(r"(?i)(read|check) (my )?(emails|gmail)")

@app.get("/mobile/intent", response_model=IntentResponse)
def mobile_intent(query: str = Query(..., min_length=1)):
    q = query.strip()

    # WhatsApp
    m = WA_RE.search(q) or WA_EN_RE.search(q)
    if m:
        contacto = (m.groupdict().get("contacto") or m.groupdict().get("contact")).strip()
        msg = m.group("msg").strip()
        return IntentResponse(
            action="whatsapp",
            whatsapp_contact=contacto,
            whatsapp_message=msg,
            say=f"Ok, enviando WhatsApp a {contacto}."
        )

    # Llamada
    m = CALL_RE.search(q) or CALL_EN_RE.search(q)
    if m:
        contacto = (m.groupdict().get("contacto") or m.groupdict().get("contact")).strip()
        return IntentResponse(
            action="call",
            call_contact=contacto,
            say=f"Llamando a {contacto}."
        )

    # Leer correos (ejemplo)
    if READ_MAIL_RE.search(q) or READ_MAIL_EN_RE.search(q):
        sample = [
            "Gmail: Mick — Confirmación de fecha para shutters",
            "Gmail: Anderson — Vauxhall next Wednesday",
        ]
        return IntentResponse(action="emails_read", emails=sample, say="Te leo los últimos correos.")

    # Saludo
    if SALUDO_RE.search(q):
        return IntentResponse(action="say", say="Hola, ¿qué necesitas?")

    # Fallback con OpenAI si tienes API
    if os.getenv("OPENAI_API_KEY") and OpenAI is not None:
        try:
            client = OpenAI()
            content = (
                "Eres un NLU breve. Devuelve un JSON con action (say|call|whatsapp|emails_read|unknown), "
                "y campos pertinentes (call_contact, whatsapp_contact, whatsapp_message, say). "
                f"Consulta del usuario: {q}"
            )
            resp = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": content}],
                response_format={"type": "json_object"}
            )
            txt = resp.choices[0].message.content
            import json
            data = json.loads(txt)
            return IntentResponse(**{k: v for k, v in data.items() if k in IntentResponse.model_fields})
        except Exception:
            pass

    return IntentResponse(action="unknown", say="No entendí. ¿Quieres llamar, enviar WhatsApp o leer correos?")
