---
name: seneca
description: Shortcut so that /seneca opens the Seneca plugin's router. Only runs when typed as /seneca.
disable-model-invocation: true
---

Load the `seneca:seneca` skill with the Skill tool and follow it, using everything the user wrote after `/seneca` as their request. If that skill isn't installed, tell them to install the Seneca plugin (`/plugin marketplace add https://github.com/htank898/Seneca.git`, then `/plugin install seneca@seneca`).
