"""Message parsing - extract data from user messages."""

import json
import logging
import re
from typing import Any
from uuid import UUID

from app.domain.ai import get_llm_router
from app.domain.ai.models import LLMRequest

logger = logging.getLogger(__name__)


def parse_data_capture_message(
    message_text: str,
    use_ai: bool = False,
    tenant_id: UUID | None = None,
) -> tuple[dict[str, Any] | None, bool]:
    """Parse data capture message to extract CEP/bairro, payment, delivery, items.
    
    Args:
        message_text: User message text
        use_ai: Whether to use AI for parsing (if True, always requires approval)
        tenant_id: Optional tenant ID for AI context
    
    Returns:
        Tuple of (parsed_data, requires_approval)
        - parsed_data: Dictionary with extracted data or None if parsing fails
        - requires_approval: True if AI was used (always requires human approval)
    """
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

    # Try AI parsing if requested
    if use_ai:
        try:
            router = get_llm_router()
            ai_prompt = f"""Extraia as informações de orçamento da seguinte mensagem do cliente:

{message_text}

Extraia e retorne APENAS um JSON válido com as seguintes chaves:
- cep_or_bairro: CEP (formato 00000-000) ou nome do bairro
- payment_method: "PIX", "Cartão" ou "Boleto"
- delivery_day: Data de entrega ou "o quanto antes"
- items: Lista de objetos com "name", "quantity" (número) e "unit" (string)

Exemplo de resposta:
{{
  "cep_or_bairro": "01310-100",
  "payment_method": "PIX",
  "delivery_day": "Amanhã",
  "items": [
    {{"name": "Cimento 50kg", "quantity": 10, "unit": "sacos"}},
    {{"name": "Areia média", "quantity": 2, "unit": "m³"}}
  ]
}}

Retorne APENAS o JSON, sem markdown ou explicações."""

            request = LLMRequest(
                prompt=ai_prompt,
                system_prompt="Você é um assistente especializado em extrair informações de pedidos de material de construção. Retorne sempre JSON válido.",
                temperature=0.3,
                tenant_id=tenant_id,
            )
            
            response = router.call(request, tenant_id=tenant_id)
            
            # Parse JSON response
            try:
                # Remove markdown code blocks if present
                content = response.content.strip()
                if content.startswith("```"):
                    # Extract JSON from code block
                    lines = content.split("\n")
                    content = "\n".join(lines[1:-1]) if len(lines) > 2 else content
                elif content.startswith("```json"):
                    lines = content.split("\n")
                    content = "\n".join(lines[1:-1]) if len(lines) > 2 else content
                
                ai_data = json.loads(content)
                
                # Validate and normalize
                if isinstance(ai_data, dict):
                    # AI was used, so requires approval
                    logger.info(f"AI parsing successful for tenant {tenant_id}, requires approval")
                    return (ai_data, True)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse AI response: {e}, falling back to regex")
                # Fall through to regex parsing
        
        except Exception as e:
            logger.error(f"AI parsing failed: {e}, falling back to regex", exc_info=True)
            # Fall through to regex parsing
    
    # Regex-based parsing (original implementation)
    # Check if we have minimum required data
    if not (cep_or_bairro and payment_method and delivery_day and items):
        return (None, False)

    return ({
        "cep_or_bairro": cep_or_bairro,
        "payment_method": payment_method,
        "delivery_day": delivery_day,
        "items": items,
    }, False)

