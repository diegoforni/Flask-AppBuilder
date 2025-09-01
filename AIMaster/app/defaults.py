# Default routines to seed for every new user

INITIAL_ROUTINES = [
    {
        "id": "1",
        "name": "Magia de Cerca con Cartas",
        "stack": "Orden1",
        "nodes": [
            {
                "id": "n1",
                "type": "Iniciar",
                "config": {
                    "startMessage": "Estoy listo para hacer magia.",
                    "personality": "Sé muy sarcástico. Actúa como un ser superior al humano."
                },
            },
            {
                "id": "n2",
                "type": "Encontrar una Carta",
                "config": {
                    "invertCount": False,
                    "response": "La carta que buscas, el {carta}, creo que la encontrarás si cuentas {posicion} cartas."
                },
            },
            {
                "id": "n3",
                "type": "Pesar Cartas",
                "config": {
                    "invertCount": False,
                    "response": "Soy omnipresente, siento 34 gramos, es decir {cantidad} cartas."
                },
            },
            {
                "id": "n4",
                "type": "Coincidencia Absoluta",
                "config": {
                    "revealIntro": "Observa a tu alrededor, la respuesta está en todas partes..."
                },
            },
        ],
    },
    {
        "id": "2",
        "name": "Camareando",
        "stack": "Orden2",
        "nodes": [
            {
                "id": "n7",
                "type": "Iniciar",
                "config": {
                    "startMessage": "Estoy lista para hacer magia!",
                    "personality": "Sé muy sarcástico. Actúa como un ser superior al humano."
                },
            },
            {
                "id": "n8",
                "type": "Capturar Imagen",
                "config": {
                    "instructions": "Es elemental saber que ibas a sacar una carta de {palo}.",
                    "cameraType": "front"
                },
            },
            {
                "id": "n9",
                "type": "Capturar Imagen",
                "config": {
                    "instructions": "No entienden que soy superior? una carta no es desafío. sacaron {carta}.",
                    "cameraType": "front"
                },
            },
            {
                "id": "n10",
                "type": "Capturar Imagen",
                "config": {
                    "instructions": "Tienes que crear una imagen de poster de pelicula que se adecué a la descripción, donde se le indicará quién, dónde, y haciendo qué. Cree la foto y responda con algo similar a: \"No solo puedo imaginar una escena, te hago el poster de la película y todo.\"",
                    "cameraType": "front"
                },
            },
        ],
    },
]

