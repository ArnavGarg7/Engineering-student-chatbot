from conversation_router import route_conversation

tests = [
    'hello',
    'HEY!!!',
    'How are you?',
    'Thanks so much',
    'goodbye!',
    'who are you',
    'help me',
    'what is the weather like?',
    'Show all CSE students from Delhi'
]

for t in tests:
    res = route_conversation(t)
    print(f"'{t}' -> {res['category']}")
