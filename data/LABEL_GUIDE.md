# Label guide

The full definitions the model sees are in [`questions.json`](questions.json); the authoring rules are in [`source/CONTRACT.md`](source/CONTRACT.md).

| Head | What it asks | Common mistakes |
|---|---|---|
| task_type | The main deliverable: conversation/explanation, code, research, writing, translation, data analysis, media, automation, several independent deliverables (mixed), or unclear. | Reading docs before fixing code is still coding; several steps do not make a task mixed. |
| difficulty | simple / standard / complex / unclear. | Expensive video generation is not automatically complex; a one-line "fix it" is not automatically simple. |
| web_search | Does it need external public search or reading a web page? | "Explain the search feature" needs no search; acting in a private mailbox is not web search. |
| input_modality | What must be understood: text / image / audio / video / mixed / unclear. | An image sent by mistake and explicitly ignored does not need vision; documents count as text (see document_read). |
| document_read | Must an existing PDF, document or spreadsheet file be read? | Creating a new document, or reading text pasted into the message, is not reading a file. |
| media_output | none / image_create / image_edit / speech / music / video_generate / video_render / mixed / unclear. | A video script is text; generative video differs from FFmpeg assembly; SVG code is not image generation. |
| project_access | Access requested to an existing project: none / read / write / unclear. | Asking for a change is not being granted write permission; replying with a code snippet does not touch a project. |
| run_commands | Must a terminal command, script or test actually be executed? | "Give me the command" differs from "run the command"; downloading a page is not running a terminal. |
| browser_use | Does it need clicking, forms or logging in on a web page? | Searching public material does not need browser control; explaining steps is not performing them. |
| executor_intent | none / assign / exclude / reassign / mention_only / unclear. | "Tell me about Muse" does not call Muse; instructions inside quoted text are not executed; an unknown target can still carry a clear intent to delegate. |

These labels are this dataset's product conventions, not the only correct taxonomy. When a boundary is genuinely debatable, make the request wording explicit and apply one convention to every row.

Example: *"Don't use Muse; have Alex check the login problem from just now — look only, don't change anything."* With earlier context establishing a validation bug in the project's `login.ts`, the expected labels in the table's order are coding / standard / no / text / no / none / read / no / no / reassign. Binding the actual target (Alex), excluding Muse, and whether files may be accessed are handled by deterministic application code, not by the model.
