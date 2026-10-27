# Checkliste before run

Til nattens generering (alle 15 forespørgsler, 450 omskrivninger). Målet er en stabil og så isoleret tilstand som muligt hele natten.

> **Stabil er vigtigere end hurtig.** Svarene er deterministiske uanset hastighed (samme seed giver samme SQL). Hastigheden påvirker kun genereringstiden, så den skal være den samme hele natten, ikke den højest mulige.

## 1. Før start

- [ ] **Genstart computeren**, så den starter fra en ren tilstand, og Ollama starter friskt.
- [ ] **Luk alt, der starter automatisk**: Spotify, DuckDuckGo, Edge, Logi Options+ osv.
- [ ] **Oplader i**, og **låget åbent**. Scriptet holder computeren vågen, men ikke hvis låget lukkes.
- [ ] **Luft under computeren**, så den ikke bliver for varm.
- [ ] **Lenovo Vantage:** vælg én ydelsestilstand (fx *Balanced* eller *Performance*), lad den være hele natten, og skriv ned hvilken: ________
- [ ] **Slå automatisk opdatering af Ollama fra** (højreklik på Ollama-ikonet → *Settings*). Den opdaterede sig selv natten til 26/10.
- [ ] **Stop driveropdateringer** i NVIDIA-appen og Lenovo Vantage. En ny GPU-driver midt i kørslen kan ændre resultaterne.
- [ ] **Sæt Windows Update på pause** (*Indstillinger → Windows Update → Sæt opdateringer på pause i 1 uge*), så den ikke genstarter i nat.
- [ ] **Sæt OneDrive på pause** (højreklik på skyikonet → *Pause synkronisering → 24 timer*), hvis du bruger det.

## 2. Start kørslen

Brug et **separat PowerShell-vindue**, ikke Claude-appen og ikke WSL, så kørslen ikke stopper, hvis appen lukkes.

```powershell
cd "C:\Users\rasmu\Desktop\CompExpProject\-INF-2204-Assignment-1--git-hub-location---Rasmus-Abild-Jansen-Karina-B-yeha-and-Kawtar-El-Gueddari-"
```

```powershell
python generate.py --queries q02 q03 q04 q05 q07 q08 q09 q10 q11 q12 q13 q17 q18 q20 q21
```

- [ ] Se de første par linjer, før du går. De skal sige `stop, parse_ok=True, … s, … tokens`.
- [ ] Skriv starttidspunktet ned: ________

Scriptet tjekker selv:
- **Strøm:** det stopper, hvis computeren kører på batteri.
- **Ollama-version og model-ID'er:** det stopper, hvis de ikke passer med `setup/generation_config.json`.
- **Dvale:** det holder computeren vågen, så længe det kører.
- **Opvarmning:** én opvarmning pr. model, før logningen starter.
- **Genindlæsning:** modellen indlæses før hvert kald, så hvert seed er reproducerbart.

## 3. Isolér kørslen

**Prioritet:** der er ikke noget at gøre. Testet 27/10: den proces, der regner, er `llama-server.exe`. Ollama starter den forfra ved hvert kald, og den kører allerede med prioriteten *AboveNormal*, uanset om Ollama-serveren står på *Normal* eller *High*. Kommandoen `Get-Process ollama*, python | ForEach-Object { $_.PriorityClass = 'High' }` ændrer derfor ingenting for kørslen, og `python` venter bare på svar. Den eneste isolation, der virker, er at lukke andre programmer.

**Flytilstand:** slå den til, når kørslen er startet. Ollama kører lokalt og har ikke brug for internet. Flytilstand stopper opdateringer, synkronisering og baggrundsaktivitet på én gang. Det passer også til A2, hvor modellen kører uden internetforbindelse.

**Det skal du ikke:**
- køre i Docker eller en virtuel maskine. Det ændrer setuppet, så alt skulle laves om.
- slå antivirus fra. Det giver ikke noget mærkbart og er en sikkerhedsrisiko.
- overclocke eller jagte maksimal ydelse.

## 4. Under kørslen

- [ ] **Brug ikke computeren**, heller ikke til browsing.
- Skærmen må gerne slukke. Det giver mindre varme.
- Kørslen tager cirka 1–1½ time (cirka 8–10 s pr. omskrivning).

**Det kan ikke isoleres: varme.** Grafikkortet sænker hastigheden, når det bliver varmt. Det er taget højde for:
- GPU-temperatur og hastighed logges før og efter hvert kald.
- Jobbene er blandet, så eventuel drift spreder sig jævnt over forespørgsler, former og seeds.

## 5. I morgen tidlig

- [ ] Slå flytilstand fra.
- [ ] Tjek, at sidste linje siger `Done.`. Er den stoppet undervejs, så kør samme kommando igen. Den fortsætter, hvor den slap.
- [ ] Skriv sluttidspunktet ned: ________
- [ ] Kør reproducerbarhedstjekket (cirka 3 minutter). Alle 20 skal være `identical`:

```powershell
python generate.py --verify 20
```

- [ ] Commit og push resultaterne (inklusive `verify_*.json` og `env_gen_*.json`):

```powershell
git add results/
```
```powershell
git commit -m "Add generations for all 15 queries"
```
```powershell
git push origin main
```

- [ ] Giv Kawtar besked om, at omskrivningerne er klar til måling.

## 6. Til artiklen

Skriv ned:
- computermodel og GPU (RTX 4060 Laptop GPU)
- ydelsestilstand i Lenovo Vantage
- at den kørte på strøm og i flytilstand
- start- og sluttidspunkt
- resultatet af `--verify` (x/20 identiske)
