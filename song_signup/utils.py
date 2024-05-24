import constance


def split_drinking_words() -> list:
    words = constance.config.DRINKING_WORDS
    return words.split(';') if words else []
