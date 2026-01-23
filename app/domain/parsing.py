"""Message parsing - extract data from user messages."""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def parse_data_capture_message(message_text: str) -> dict[str, Any] | None:
    """Parse data capture message to extract CEP/bairro, payment, delivery, items.

    This is a simple parser for MVP. In production, might use NLP/LLM.

    Args:
        message_text: User message text

    Returns:
        Dictionary with:
        - cep_or_bairro: str | None
        - payment_method: str | None
        - delivery_day: str | None
        - items: list[dict] | None
        Or None if parsing fails
    """
    text = message_text.strip().upper()

    # Extract CEP or bairro
    cep_or_bairro = None
    # Look for CEP pattern: 5 digits - 3 digits
    cep_match = re.search(r"\b(\d{5}[- ]?\d{3})\b", message_text)
    if cep_match:
        cep_normalized = cep_match.group(1).replace(" ", "-")
        # Validate CEP format (should be 8 digits)
        if len(cep_normalized.replace("-", "")) == 8:
            cep_or_bairro = cep_normalized
    else:
        # Look for bairro keywords
        bairro_keywords = ["BAIRRO:", "BAIRRO", "LOCALIZAÇÃO:", "LOCALIZAÇÃO"]
        for keyword in bairro_keywords:
            if keyword in text:
                # Extract text after keyword
                parts = text.split(keyword, 1)
                if len(parts) > 1:
                    bairro = parts[1].split("\n")[0].strip()
                    if bairro:
                        cep_or_bairro = bairro
                        break

    # Extract payment method
    payment_method = None
    payment_keywords = {
        "PIX": ["PIX"],
        "Cartão": ["CARTÃO", "CARTAO", "CREDITO", "CRÉDITO", "DEBITO", "DÉBITO"],
        "Boleto": ["BOLETO"],
    }
    for method, keywords in payment_keywords.items():
        if any(kw in text for kw in keywords):
            payment_method = method
            break

    # Extract delivery day
    delivery_day = None
    delivery_keywords = {
        "o quanto antes": ["QUANTO ANTES", "URGENTE", "IMEDIATO"],
        "Amanhã": ["AMANHÃ", "AMANHA"],
        "Hoje": ["HOJE"],
    }
    for day, keywords in delivery_keywords.items():
        if any(kw in text for kw in keywords):
            delivery_day = day
            break

    # If not found, look for date patterns or "delivery" keywords
    if not delivery_day:
        if "ENTREGA" in text or "DELIVERY" in text:
            # Extract text after keyword
            for keyword in ["ENTREGA:", "ENTREGA", "DELIVERY:"]:
                if keyword in text:
                    parts = text.split(keyword, 1)
                    if len(parts) > 1:
                        delivery_day = parts[1].split("\n")[0].strip()
                        break

    # Extract items (simple pattern matching)
    items = []
    # Look for item patterns like "Cimento 50kg: 10 sacos" or "Cimento: 10"
    # This is very basic - in production would use NLP
    item_pattern = r"[-•]\s*([^:]+):\s*(\d+(?:[.,]\d+)?)\s*(\w+)?"
    matches = re.findall(item_pattern, message_text, re.IGNORECASE)
    for match in matches:
        item_name = match[0].strip()
        if not item_name:
            continue  # Skip empty names

        quantity_str = match[1].replace(",", ".")
        try:
            quantity = float(quantity_str)
            if quantity <= 0:
                continue  # Skip invalid quantities
        except ValueError:
            continue  # Skip if not a valid number

        unit = match[2].strip() if match[2] else "un"
        items.append({
            "name": item_name,
            "quantity": quantity,
            "unit": unit,
        })

    # Check if we have minimum required data
    if not (cep_or_bairro and payment_method and delivery_day and items):
        return None

    return {
        "cep_or_bairro": cep_or_bairro,
        "payment_method": payment_method,
        "delivery_day": delivery_day,
        "items": items,
    }

