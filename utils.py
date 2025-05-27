import pickle

def get_nochat_channels():
    try:
        with open('nochat_channels.pk1', 'rb') as dbfile:
            no_chat_channels = pickle.load(dbfile)
    except (FileNotFoundError, EOFError):
        no_chat_channels = []
        with open('nochat_channels.pk1', 'wb') as dbfile:
            pickle.dump(no_chat_channels, dbfile)
    return no_chat_channels


def load_rp_sessions():
    try:
        with open('rp_sessions.pk1', 'rb') as dbfile:
            rp_sessions = pickle.load(dbfile)
    except (FileNotFoundError, EOFError):
        rp_sessions = {}
    return rp_sessions


def save_rp_sessions(rp_sessions):
    with open("rp_sessions.pk1", "wb") as file:
        pickle.dump(rp_sessions, file)