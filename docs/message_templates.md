# Message Templates (PT-BR)

All user-facing messages are in Brazilian Portuguese (PT-BR).

## Data Capture Prompt (Single Block)

```
Olá! 👋

Para gerar seu orçamento, preciso das seguintes informações:

📍 *Localização:* [CEP ou bairro]
💳 *Forma de pagamento:* [PIX / Cartão / Boleto]
📅 *Dia de entrega:* [Data ou "o quanto antes"]
📦 *Itens:* [Lista de produtos com quantidades]

Exemplo:
📍 CEP: 01310-100 ou Bairro: Centro
💳 PIX
📅 Amanhã
📦
- Cimento 50kg: 10 sacos
- Areia média: 2m³
- Tijolo comum: 500 unidades
```

## Quote Message (Single Message)

```
✅ *Orçamento Gerado*

*Itens:*
• Cimento 50kg (10 sacos): R$ 450,00
• Areia média (2m³): R$ 180,00
• Tijolo comum (500 un): R$ 350,00

*Subtotal:* R$ 980,00
*Frete:* R$ 45,00
*Desconto PIX (5%):* -R$ 49,00
━━━━━━━━━━━━━━━━
*Total:* R$ 976,00

💳 *Forma de pagamento:* PIX
📅 *Entrega:* Amanhã (15/01/2024)

⏰ *Válido até:* 16/01/2024 às 18:00

Para agendar a entrega, responda:
✅ *Confirmar* ou *Sim*

Ou envie sua dúvida que te ajudo! 😊
```

## Approval Required Fallback

```
Olá! 👋

Recebi sua solicitação. Para garantir o melhor atendimento, nossa equipe está analisando seu pedido e entrará em contato em breve.

Você receberá uma resposta em até 2 horas úteis.

Obrigado pela compreensão! 🙏
```

## Scheduling Confirmation

```
✅ *Entrega Agendada!*

Confirmamos seu pedido:
📦 *Itens:* [resumo]
💰 *Total:* R$ [valor]
📅 *Data de entrega:* [data] às [hora]
📍 *Endereço:* [endereço do CEP/bairro]

*Próximos passos:*
1. Aguarde nosso contato para confirmar o horário exato
2. Enviaremos o link de pagamento via PIX

Obrigado pela preferência! 🎉
```

## Error Messages

### Unknown SKU
```
Desculpe, não encontrei o produto "[SKU]" no nosso catálogo. 

Pode verificar o nome ou código do produto e enviar novamente?

Ou digite *catalogo* para ver nossos produtos disponíveis.
```

### Invalid Data Format
```
Desculpe, não consegui entender algumas informações. 

Por favor, envie novamente no formato:
📍 CEP ou bairro
💳 Forma de pagamento
📅 Dia de entrega
📦 Lista de itens

Obrigado! 😊
```

### Quote Expired
```
Este orçamento expirou. 

Para gerar um novo orçamento, envie suas informações novamente:
📍 CEP ou bairro
💳 Forma de pagamento
📅 Dia de entrega
📦 Lista de itens
```

## Template Variables

When implementing, use a template engine (e.g., Jinja2) with these variables:

- `{items}` - List of items with quantities and prices
- `{subtotal}` - Subtotal amount
- `{freight}` - Freight cost
- `{discount_pct}` - Discount percentage
- `{discount_amount}` - Discount amount
- `{total}` - Total amount
- `{payment_method}` - Payment method
- `{delivery_day}` - Delivery day
- `{valid_until}` - Quote expiration datetime
- `{contact_name}` - Contact name (if available)


