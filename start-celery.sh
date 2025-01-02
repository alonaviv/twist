#!/bin/bash
celery -A twist worker -Q "celery" -l INFO &
celery -A twist worker -Q "parser_AzLyricsParser_queue" -n parser_azlyrics -l INFO &
celery -A twist worker -Q "parser_AllMusicalsParser_queue" -n parser_allmusicals -l INFO &
celery -A twist worker -Q "parser_GeniusParser_queue" -n parser_genius -l INFO &
celery -A twist worker -Q "parser_TheMusicalLyricsParser_queue" -n parser_themusical -l INFO &
celery -A twist worker -Q "parser_LyricsTranslateParser_queue" -n parser_lyricstranslate -l INFO &
celery -A twist worker -Q "parser_ShironetParser_queue" -n parser_shironet -l INFO &
wait
