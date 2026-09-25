# What was actually tested

Target: **standalone Quest, Beat Saber 1.45.1_27839 (version code 3071), Scotland2**. Most runtime observations were on one Quest 3 with a combined experimental mod installation. They do not establish support on every headset or every feature.

| Feature | Evidence and limit |
| --- | --- |
| Custom levels / SongCore | User opened a custom level and confirmed audio and notes. |
| Better Song Search / More Songs | User confirmed menus, search results, and a song download. |
| Better Song List sorting | User confirmed sorting worked. |
| Noodle Extensions | User confirmed a tested Noodle map played without problems. |
| Chroma | User confirmed notes in Onii-Chan Baka Hentai and colors in Blue (Da Ba Dee) after fixes. This does not validate all Chroma events or maps. |
| Mapping Extensions | Startup and targeted compatibility fixes were checked; feature coverage across maps remains limited. |
| Song-selection stutter | A beatsaber-hook directory check was corrected; redundant process creation disappeared from the measured hot path, and the user confirmed ordinary selection became smooth. This is not a guarantee of zero frame drops. |
| CongXinJian | User confirmed manual offsets. v5 fixes a startup null-reference abort and reached the Continue screen, with a bounded 40-second startup observation free of that abort. Eight sampled Auto Pos line writes across both hands matched independently read visual-anchor direction/root at logged precision. The user confirmed Auto Pos direction and position are correct. Auto Rot and gameplay/menu-return coverage remain pending. |
| Windows / Linux installer | 29 offline archive/transaction/mock-ADB tests passed on both GitHub runners; the PowerShell 5 wrapper plan passed on Windows. Physical Windows headset installation and the full WSL build flow were not exercised. |
| Multiplayer / score submission | Not established. Optional packages are not proof that online services work. |
| Other cosmetic and utility mods | Generally bounded startup checks; individual controls need separate testing. |

The DADADADA Mario bridge remained visually questionable to the user. Similar appearance was observed in the older-version comparison; the work does not prove every detail is correct or assign the issue conclusively to the game or map.

## Local builds

A successful compile/link verifies a build stage. Rebuilt libraries can have different hashes from the binaries used for the observations above. The local build receipt identifies the exact inputs and resulting hashes; it is not a runtime certification.

## Reporting problems

Include the headset model, full game version, selected package versions, song/map ID and difficulty, and clear reproduction steps. Distinguish a startup failure, menu stutter, missing notes and a visual mismatch. Review logs before sharing them: they can include account names, song paths and device information.

No private gameplay recordings, account data, personal settings or game installation files are included here.
