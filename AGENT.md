# Блок для агента — скопируй и вставь

Ниже — всё, что нужно сказать агенту, чтобы он вёл дело этого проекта через Elephant. Скопируй текст под чертой в файл инструкций своего harness: Claude Code → `CLAUDE.md` · Codex → `AGENTS.md` · Gemini → `GEMINI.md` · Cursor → `.cursor/rules/` · Copilot → `.github/copilot-instructions.md`.

Больше подключать нечего: дальше инструмент рассказывает о себе сам — `el` печатает состояние и что поправить, `el help <topic>` выдаёт знание дозами в момент нужды.

---

## Elephant — память работы в `.cases/`

- Дело этого проекта ведётся командой `el`. **Начинай сессию с `el`**: она печатает, где дело стоит, что дальше и блок `Order` — что не на месте и какой командой поправить. Устройство целиком — `el help start`, дальше `el help <topic>`.
- **Пиши только через `el`**, README / TODO / JOURNAL руками не трогай — правка ловится отпечатком. Решение → `el log DECISION "что · вместо чего · почему"`; результат → `el log RESULT "…"`; сделанный пункт → `el todo done N.M "что вышло"`.
- **Заканчивая — снова `el`**: если `Order` говорит «State is behind», обнови строку State (`el readme set next "…"`). Проверить дело против правил — `el check`.
- Нет команды `el` → `git clone https://github.com/MykhailoDmytriakha/elephant-cli`, затем `./elephant-cli/install.sh`.
