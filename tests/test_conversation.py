from conversation.history import ConversationHistory


def test_aggiunta_messaggio():
    history = ConversationHistory()

    history.add_message("user", "Ciao")

    assert history.get_messages() == [
        {
            "role": "user",
            "content": "Ciao",
        }
    ]



def test_salva_e_carica_da_file(tmp_path):
    file_path = tmp_path / "history.json"

    history = ConversationHistory()
    history.add_message("user", "Ciao")
    history.add_message("assistant", "Ciao a te!")
    history.save_to_file(file_path)

    nuova_history = ConversationHistory()
    nuova_history.load_from_file(file_path)

    assert nuova_history.get_messages() == history.get_messages()


def test_load_from_file_senza_file_esistente(tmp_path):
    file_path = tmp_path / "non_esiste.json"

    history = ConversationHistory()
    history.load_from_file(file_path)

    assert history.get_messages() == []




def test_get_recent_messages_restituisce_solo_gli_ultimi():
    history = ConversationHistory()

    for i in range(5):
        history.add_message("user", f"messaggio {i}")

    recenti = history.get_recent_messages(2)

    assert [m["content"] for m in recenti] == ["messaggio 3", "messaggio 4"]