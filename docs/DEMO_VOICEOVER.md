# HeyList — Demo voiceover

The voice script for the cut in `video-test/` (`output/demo_v4.mp4`, 2:56; with the voice: `demo_v5.mp4`). Each cue below is one audio file: generate it with the AI voice, save it as `video-test/voice/NN.mp3`, and it goes into the video at its start time. Written 2026-11-07.

**About 280 words** over 2:56, so the picture has room to breathe. Each cue has a window (from its start to the next cue); the cue's audio should end inside it. At a natural AI voice pace (about 2.5 words a second), every cue fits with a second or more to spare.

## How to make the voice

1. Use one voice and the same settings for every cue. Pick a warm, confident voice, at normal speed (not slowed).
2. Paste each cue's text on its own and download it as `01.mp3`, `02.mp3` and so on (any audio format works).
3. Put the files in `video-test/voice/`. Then either add them on vedit's **Sound** tab (Starts at = the cue's start), or ask Claude to place them all.
4. If a cue runs past its window, regenerate it a little faster (1.05×) or drop its last sentence; the screen already says it in the labels.

The text is written to be read aloud: numbers are words, there are no symbols, and a full stop is a short pause.

## Cues

| # | Starts (as placed in demo_v5) | Window | On screen |
|---|---|---|---|
| 01 | 0:00.3 | 8.5 s | HeyList title card, then the 82% card |
| 02 | 0:09.9 | 13 s | Typing "Photo trip this weekend", the AI writing the list |
| 03 | 0:23.0 | 15.5 s | Marking the camera, lenses, tripod "Already have"; 5 of 10 |
| 04 | 0:39.5 | 11 s | Shop this list for me, the AI finding products, the cart |
| 05 | 0:52.6 | 17 s | PayPal Pay in 4, approved, 6 of 10 |
| 06 | 1:07.4 | 19.5 s | Ben opens the link, joins by name, picks his items |
| 07 | 1:31.6 | 11 s | Ben pays with PayPal; 8 of 10 |
| 08 | 1:42.8 | 18.5 s | Jerry's phone: snaps the receipt, the AI reads it |
| 09 | 1:55.3 | 14 s | Frozen close-up of the receipt check, then checked off |
| 10 | 2:09.3 | 17.6 s | The snacks, paid with PayPal |
| 11 | 2:27.6 | 2.3 s | 10 of 10 |
| 12 | 2:29.4 | 11 s | Money: how it adds up, who paid what |
| 13 | 2:41.2 | 11.5 s | The reminder for Jerry; "2 payments and everyone's even" |
| 14 | 2:51.7 | 4.5 s | Closing card |

### 01 · 0:00.3

```text
Group trips are fun. The money isn't. Eighty-two percent of people would rather overpay than argue about it.
```

### 02 · 0:09.9

```text
Meet HeyList. I type one sentence: a photo trip this weekend. In seconds, AI writes the whole gear list, priced at real stores.
```

### 03 · 0:23.0

```text
I already own the camera, the lenses and the tripod, so I mark them, and they drop off the budget. Half the list is done before we spend a cent.
```

### 04 · 0:39.5

```text
For the rest, the AI shops for me. It finds real products from real stores and fills a cart. I check it, and pay once.
```

### 05 · 0:52.6

```text
With PayPal Pay in 4, it splits into four interest-free payments, right at checkout. Approved, and it's checked off for everyone.
```

### 06 · 1:07.4

```text
Then I share the link with Ben. No app, no sign-up, just his name. He picks the things he's covering.
```

### 07 · 1:31.6

```text
And pays with PayPal too. The list updates for all of us, live.
```

### 08 · 1:42.8

```text
Jerry shopped in a real store, so he just snaps the receipt. AI reads every line and matches it to our list. That SD card? It's our memory cards.
```

### 09 · 1:55.3

```text
Every price is checked against the receipt's total, so nothing slips through. One tap, and it's checked off, with the receipt as proof.
```

### 10 · 2:09.3

```text
I pay for the last item, the snacks, with PayPal. Same quick checkout, and every payment lands on the list by itself.
```

### 11 · 2:27.6

```text
Ten out of ten.
```

### 12 · 2:29.4

```text
Money shows where every dollar went: the items, the fees, and exactly who paid what.
```

### 13 · 2:41.2

```text
HeyList writes Jerry a friendly reminder, and works out the fewest payments. Two PayPal payments, and everyone's even, to the cent.
```

### 14 · 2:51.7

```text
HeyList. Plan it with AI. Settle it with PayPal.
```

## Notes

- **Say "HeyList" as "hey list".** If the voice runs it together, write "Hey List" in that cue only.
- **Cue 05:** if the voice reads "Pay in 4" oddly, write "Pay in four".
- **Cue 12 doesn't mention tax,** because on this recording Money shows the receipt's $1.62 under "Tip and fees" and sales tax as $0.00. If you re-record with the tax read as tax, change it to "the items, the tax, and exactly who paid what".
- **Music:** if you add any, keep it around 10–15% volume under the voice (Sound tab: volume 0.12, loop on, fade in 1, fade out 2).
- **If the cut changes,** the start times move with it. `output/<name>_vN.json` lists where every scene and shot lands, and Claude can re-time the cues from it.
