when: проверить el без права записи · read-only sandbox · Operation not permitted · Permission denied · traceback PermissionError · отказ говорит nothing was written, а файл изменён · откат команды неполный

# Проверить el там, где писать нельзя

Признак: агент работает в песочнице только на чтение (Codex read-only, папка без права записи, общий диск), и el падает traceback, отвечает exit 0 над тем, что не записалось, или говорит «nothing was written», а на диске что-то осталось.

Как el устроен (партия 61, 1.83.4): запрет записи от системы — отказ el у двери записи (`store.denied`, exit 4, «cannot write <файл>» / «cannot move A → B», последней строкой двери, которым запись не нужна). Взгляд — вход, `el status`, `el todo`, `el order`, `todo show/brief` — показывает дело и одной строкой называет, что не обновил. Команда записи, которой система отказала где угодно по пути, в конце отказывается целиком (`store.LAST_DENIED`, `main._a_write`), а откат (`store.rollback`) возвращает байты, ссылки как ссылки, права, время изменения, убирает созданные папки и отметки сессии (рука, `.wrote`, счётчик вопросов); что вернуть не смог — называет.

```sh
T=$(mktemp -d) && cd "$T" && git init -q && export EL_HANDS_DIR="$T/hands" EL_SESSION=rotest01
el case new shop --goal "the shop works" && el phase open 1 Work --goal "the shop works"
chmod -R a-w .cases                                  # как песочница: писать в дело нельзя
el; el todo; el order                                # взгляд: exit 0, строка «read-only here … not refreshed»
el log DECISION "x"; echo $?                         # запись: exit 4, без traceback, файлы те же
chmod -R u+w .cases
```

Края, которые нашла приёмка (27 кругов): файл — ссылка в закрытую папку (`ln -s`), правленный руками TODO (пересборка — запись внутри чтения), закрытая папка рук (`chmod 500 "$EL_HANDS_DIR"`), нет временной папки, `EL_CASE` на другое или неоднозначное дело, журнал со временем в будущем (`touch -t`), umask 0222, исполняемый файл в `mv`. На macOS полный запрет — `sandbox-exec -p '(version 1)(allow default)(deny file-write* (subpath "<папка>"))' el …`; внутри песочницы Codex он запрещён, там хватает `chmod`.

Сверка: снимок до и после (байты, права, `mtime`, список файлов и папок, файлы `$EL_HANDS_DIR` кроме `-calls.json` и `-walls.jsonl` — они считают каждый вызов нарочно) и каждая напечатанная дверь, исполненная через `shlex` как есть. Тесты той же формы — `tests/test_read_only_1108.py`.
