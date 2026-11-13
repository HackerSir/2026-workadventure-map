/// <reference types="@workadventure/iframe-api-typings" />

import { postState, wait } from "./utils";
import { addCard, initProgress, QUESTS } from "./living/progress";
import { loadSaved, save } from "./living/saved";
import { initSound, loop, sfx, stopAllLoops } from "./living/sound";
import { announce, closeDialog, initUi, openPage, say, setObjective, setOnline, type Speaker } from "./living/ui";

// Side quest: find security mistakes in an office. It never counts towards the prize.
const TIME_LIMIT = 120;
const PASS = 4;
const AUDITOR: Speaker = { name: "資安稽核員", portrait: "stand4" };
const SELF: Speaker = { name: "你" };

// Keys match FINDINGS and DECOYS in tools/build_office.py.
const FINDINGS: Record<string, { look: string; reveal: string }> = {
  sticky: {
    look: "螢幕邊框上貼著一張黃色便利貼。",
    reveal: "上面寫著「VPN 密碼：Hackersir2026!」。路過的人、清潔人員、視訊會議的鏡頭，全都看得到。",
  },
  unlocked: {
    look: "座位上沒人，椅子被推開了，螢幕還亮著。",
    reveal: "電腦沒鎖就離開。任何人坐下來，都能用他的身分寄信、看資料。離開座位記得按 Win+L。",
  },
  phish: {
    look: "收件匣跳出一封新信：「您的 Office 365 帳號將於 24 小時內停用」。",
    reveal: "",
  },
  usb: {
    look: "地上有一支沒人認領的 USB 隨身碟。",
    reveal: "撿到的 USB 很可能是攻擊者故意丟的，插上去就可能中毒。交給資訊單位，不要自己插。",
  },
  trash: {
    look: "垃圾桶裡露出一張蓋著紅色「機密」章的文件。",
    reveal: "機密文件整張丟進垃圾桶，翻垃圾就拿得到。要用碎紙機處理。",
  },
};

const DECOYS: Record<string, { look: string; verdict: string }> = {
  locked: { look: "這台電腦的螢幕顯示著鎖頭圖示。", verdict: "螢幕已經鎖定，這是正確的好習慣。" },
  shredder: { look: "一台碎紙機，出口塞滿了碎紙條。", verdict: "有人乖乖把文件碎掉了，沒問題。" },
  whiteboard: { look: "白板上畫著幾條彩色的會議重點。", verdict: "只是一般的待辦事項，沒有寫密碼或機密，沒問題。" },
  serverdoor: { look: "機房的門關著，旁邊有一台刷卡機。", verdict: "門有關好，要刷卡才能進去，這是正確的門禁。" },
};

const found = new Set<string>();
let remaining = TIME_LIMIT;
let running = false;
let timer: ReturnType<typeof setInterval> | undefined;

const status = () => `找出資安問題 ${found.size}/${Object.keys(FINDINGS).length}　剩 ${remaining} 秒`;

const allFound = () => found.size === Object.keys(FINDINGS).length;

const markFound = (id: string) => {
  found.add(id);
  WA.room.showLayer(`found/${id}`);
  sfx("correct", 0.5);
  setObjective(status());
  if (allFound()) {
    // Stop the clock now, but leave time to read the last explanation before the results.
    clearInterval(timer);
    setObjective(`全部找到了！還剩 ${remaining} 秒`);
  }
};

/** Call after the last finding's explanation has been shown. */
const finishIfAllFound = async () => {
  if (running && allFound()) {
    await wait(4000);
    if (running) {
      await finish();
    }
  }
};

const resetRoom = () => {
  for (const id of Object.keys(FINDINGS)) {
    WA.room.hideLayer(`found/${id}`);
  }
  found.clear();
};

const finish = async () => {
  running = false;
  clearInterval(timer);
  setObjective("");
  closeDialog();

  const score = found.size;
  const best = Number(loadSaved("hsOfficeBest")) || 0;
  if (score > best) {
    await save("hsOfficeBest", score);
  }

  const passed = score >= PASS;
  sfx(passed ? "card" : "wrong", 0.55);
  const isNew = passed && (await addCard("office"));
  if (passed) {
    announce(isNew ? `辦公室找碴通過！拿到了「${QUESTS.office.reward}」` : `辦公室找碴通過！找到 ${score} 個問題`);
    postState("office/finish");
  }
  const missed = Object.keys(FINDINGS).filter(id => !found.has(id));
  const hint = missed.length ? `漏掉的：${missed.map(id => FINDINGS[id].look.replace(/。$/, "")).join("；")}。` : "全部都找到了，太強了！";
  const choice = await say(
    AUDITOR,
    `${allFound() ? `只花了 ${TIME_LIMIT - remaining} 秒就全部找到！` : passed ? "時間到，做得好！" : "時間到，還差一點。"}你找到 ${score} 個問題。${isNew ? `這張「${QUESTS.office.reward}」給你。` : ""}${hint}`,
    [
      { id: "again", label: "再挑戰" },
      { id: "leave", label: "回小鎮" },
    ]
  );
  if (choice === "again") {
    start();
  } else if (choice === "leave") {
    stopAllLoops();
    WA.nav.goToRoom("map.tmj#hsFromOffice");
  }
};

const start = () => {
  resetRoom();
  closeDialog();
  remaining = TIME_LIMIT;
  running = true;
  setObjective(status());
  clearInterval(timer);
  timer = setInterval(() => {
    remaining--;
    setObjective(status());
    if (remaining <= 0) {
      finish();
    } else if (remaining === 10) {
      sfx("someone", 0.4);
    }
  }, 1000);
};

type PhishResult = { found: number; total: number; at: number };
let mailOpen = false;

/** Resolves with the mail page's result, or null if the timer ran out or the page went away. */
const waitForMail = (openedAt: number) =>
  new Promise<PhishResult | null>(resolve => {
    const fresh = (value: unknown) => {
      const result = value as PhishResult | undefined;
      return result && result.at >= openedAt ? result : null;
    };
    const done = (result: PhishResult | null) => {
      clearInterval(poll);
      subscription.unsubscribe();
      resolve(result);
    };
    const subscription = WA.player.state.onVariableChange("hsPhish").subscribe(value => {
      const result = fresh(value);
      if (result) done(result);
    });
    // The change event is not the only way in: reading the variable also catches a result whose
    // event was missed, and an empty list of pages means the player closed the mail some other way.
    const poll = setInterval(async () => {
      const result = fresh(WA.player.state.loadVariable("hsPhish"));
      if (result || !running) {
        done(result);
        return;
      }
      const pages = await WA.ui.website.getAll();
      if (!pages.some(page => page.url.includes("phish"))) {
        done(fresh(WA.player.state.loadVariable("hsPhish")));
      }
    }, 500);
  });

const inspectPhishing = async () => {
  if (mailOpen) {
    return;
  }
  mailOpen = true;
  const openedAt = Date.now();
  const close = await openPage("phish");
  const result = await waitForMail(openedAt);
  await close().catch(() => {});
  mailOpen = false;
  if (!result || !running) {
    return;
  }
  if (result.found >= 4) {
    markFound("phish");
    await say(AUDITOR, `你在信裡抓到 ${result.found}/${result.total} 個破綻。這是一封釣魚信，點了連結或回傳密碼，帳號就被盜了。`);
    await finishIfAllFound();
  } else {
    sfx("wrong", 0.4);
    await say(AUDITOR, `只找到 ${result.found}/${result.total} 個破綻，這封信還沒被你看穿。再看一次？`);
  }
};

const inspect = async (id: string) => {
  if (!running) {
    return;
  }
  if (found.has(id)) {
    await say(SELF, "這個已經記下來了。");
    return;
  }
  const finding = FINDINGS[id];
  const choice = await say(SELF, finding.look, [{ id: "check", label: id === "phish" ? "打開信件" : "仔細檢查" }]);
  if (choice !== "check" || !running) {
    return;
  }
  if (id === "phish") {
    closeDialog();
    await inspectPhishing();
    return;
  }
  markFound(id);
  await say(AUDITOR, finding.reveal);
  await finishIfAllFound();
};

const inspectDecoy = async (id: string) => {
  if (!running) {
    return;
  }
  const decoy = DECOYS[id];
  const choice = await say(SELF, decoy.look, [{ id: "check", label: "仔細檢查" }]);
  if (choice === "check" && running) {
    await say(AUDITOR, decoy.verdict);
  }
};

WA.onInit()
  .then(async () => {
    initSound();
    await initUi();
    loop("bgm_kahoot", 0.16);
    await initProgress();

    // Players are counted per map, so this is how many people are in the office.
    await WA.players.configureTracking({ players: true, movement: false });
    const refreshCount = () => setOnline(Array.from(WA.players.list()).length + 1);
    refreshCount();
    WA.players.onPlayerEnters.subscribe(refreshCount);
    WA.players.onPlayerLeaves.subscribe(refreshCount);

    for (const id of Object.keys(FINDINGS)) {
      WA.room.area.onEnter(`find_${id}`).subscribe(() => inspect(id));
      WA.room.area.onLeave(`find_${id}`).subscribe(() => id !== "phish" && closeDialog());
    }
    for (const id of Object.keys(DECOYS)) {
      WA.room.area.onEnter(`decoy_${id}`).subscribe(() => inspectDecoy(id));
      WA.room.area.onLeave(`decoy_${id}`).subscribe(closeDialog);
    }

    await wait(600);
    sfx("talk_keeper", 0.35);
    const choice = await say(
      AUDITOR,
      `歡迎來到辦公室。這裡藏著 ${Object.keys(FINDINGS).length} 個資安問題，也有看起來可疑但其實沒問題的東西。走到東西前面檢查，${TIME_LIMIT} 秒內找到 ${PASS} 個就過關。`,
      [{ id: "go", label: "開始計時" }]
    );
    if (choice === "go") {
      start();
    }
  })
  .catch(e => console.error(e));

export {};
