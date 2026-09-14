when: Order говорит «State is behind» · «file(s) without summary» · «folder has no description» · «≈ … is verbatim in» · «limit 24» · README Links устарел · вход Elephant длинный · беспорядок в docs/

# Держать дело в порядке

Каждый `el` заканчивается блоком `## Order` — по строке на то, что не на месте, с командой, которая это чинит. Пусто — `✓ everything in place`. То же в `el order`; `el check` печатает те же строки предупреждениями.

| строка Order | что сделать |
|---|---|
| `State is behind: N entries since as of …` | прочитать `State`: что-то изменилось → `el readme set next "…"`; верен как есть → `el readme touch` (двигает только якорь `as of`); переписать целиком — `el readme --file README.md` |
| `N file(s) without summary:` | вторая строка файла: `summary: одна фраза` — описания, уже написанные в Links, переносит `el order --adopt` |
| `folder docs/ has no description` | `el readme add links "docs/ — что здесь"` — строка папки твоя, файлы под ней el допишет сам |
| `a.md ≈ b.md: NN % of a.md's text is verbatim in b.md` | назвать разницу в `summary:` обоих — или слить, если это копия. Считаются дословные фразы (тройки слов подряд), не словарь: два документа об одном предмете делят имена и даты и остаются двумя документами |
| `x.md is NN KB (limit 24)` | разделить по summary или сократить. Бюджета папки нет: счётчик байтов не отличает рабочие документы от воды |
| `overdue: N.M «…» was due …` | сделано → `el todo done N.M`; сдвинулось → `el todo due N.M <дата>`; больше не нужно → `el todo cancel N.M "почему"` |
| `N broken link(s): file → target` | поправить ссылку руками или переносить файлы через `el mv old new` — ссылки переписываются сами; файл уже переехал мимо el → `el relink old new` (переписывает и журнал, который руками не тронуть); файла нет насовсем или ссылка была примером без обратных кавычек → `el relink old none` — ссылка становится текстом в кавычках. В README/TODO мёртвая ссылка — нарушение `check` (F16), в документах, файлах фаз и журнале — только эта строка |
| `State` держит строку, которая перестала быть правдой | `el readme set <prefix> ""` или `el readme drop state <prefix>` — строки `progress:`/`last:`/`as of:` держит el, их не убрать и не задать |
| строка `Decisions`/`Context`/`Problems` устарела | `el readme edit decisions 3 "…"` — на месте, порядок сохранён; `readme set` пишет только `State` и на чужой префикс отказывает, называя секцию и команду |
| `N item(s) without a link to their material` | правило дела F17 включено (строка Context `rule: items link their material`): в текст пункта — `[имя](docs/файл.md)` через `el todo edit N.M "…"`; не нужно в этом деле — убрать строку Context |
| `N.M is after N.K, which is gone` | зависимость снята или удалена: перевязать `el todo after N.M "…"` (или `none`) — либо снять сам пункт `el todo cancel N.M "почему"` |
| `nested case X: README unparsable` | ребёнок сломан и держит родителя открытым (F18): `el --case X check`, починить через `el migrate` или команды |
| `cannot close phase N: open items …` (отказ) | у каждого пункта два конца (F20): `el todo done N.M "что вышло"` или `el todo cancel N.M "почему"`; вся фаза не нужна — `el phase cancel N "почему"` |
| `extra file in the case root` | унести в папку по виду (`docs/`, `research/`, `logs/`) |
| `pending X.recover.md` | внести строки командами Elephant, потом `rm` |

Почему так: предел на README один сдвигал воду этажом ниже — новый файл дёшев, слить два никто не делал. Теперь нижний слой виден сверху, а верх (Links, `last:`, `progress:`) рисуется из него и не гниёт.
