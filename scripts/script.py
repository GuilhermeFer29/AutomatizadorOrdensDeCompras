import csv
import random
import uuid

# Definição das categorias e itens
categories = {
    "Ferragens e Acessórios": [
        "Grampos galvanizados",
        "Pregos sem cabeça",
        "Parafusos soberbos",
        "Cantoneiras metálicas",
        "Rodízios plásticos",
        "Rodízios de silicone"
    ],
    "Ferramentas e Insumos de Produção": [
        "Grampeadores pneumáticos",
        "Pistolas de cola quente",
        "Cola spray",
        "Cola de contato",
        "Agulhas para costura de estofados"
    ],
    "Acabamentos": [
        "Botões encapados",
        "Pespontos decorativos",
        "Zíperes reforçados",
        "Velcros industriais"
    ],
    "Estruturas de Madeira": [
        "Chapas MDF",
        "Chapas OSB",
        "Sarrafos de pinus"
    ],
    "Espumas e Enchimentos": [
        "Espuma D23",
        "Espuma D28",
        "Espuma viscoelástica",
        "Fibras siliconadas",
        "Mantas acrílicas"
    ],
    "Tecidos e Revestimentos": [
        "Suede",
        "Linho",
        "Chenille",
        "Jacquard floral"
    ],
    "Colas e Adesivos": [
        "Cola spray",
        "Cola de contato",
        "Cola quente bastão"
    ]
}

# Função para gerar nomes dinâmicos
def generate_name(base_name):
    attributes = [
        f"{random.randint(10, 100)}mm",
        f"{random.randint(1, 5)}x{random.randint(1, 5)}cm",
        f"{random.randint(1, 3)}L",
        f"{random.randint(1, 2)}kg",
        f"{random.randint(1, 2)}x{random.randint(1, 2)}m"
    ]
    return f"{base_name} {random.choice(attributes)}"

# Função para gerar SKU único
def generate_sku():
    return str(uuid.uuid4())[:8].upper()

# Função para gerar estoque e estoque mínimo
def generate_stock():
    return random.randint(50, 400), random.randint(10, 80)

# Gerar 1000 registros
rows = []
for _ in range(3000):
    category = random.choice(list(categories.keys()))
    base_name = random.choice(categories[category])
    name = generate_name(base_name)
    sku = generate_sku()
    stock, minimum_stock = generate_stock()
    rows.append([name, sku, category, stock, minimum_stock])

# Escrever no arquivo CSV
output_file = "/home/guilhermedev/Documentos/Automação Inteligente de Ordens de Compra para Pequenas e Médias Indústrias/data/products_seed.csv"
with open(output_file, mode="w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(["nome", "sku", "categoria", "estoque_atual", "estoque_minimo"])
    writer.writerows(rows)

print(f"Arquivo {output_file} gerado com 1000 registros.")