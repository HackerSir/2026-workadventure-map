/// <reference types="@workadventure/iframe-api-typings" />

import { postState, showToast, wait } from "./utils";
import { loadSaved } from "./living/saved";
import cryptoData from "./crypto_data.json";
import { initPresence, stepInSnow } from "./living/presence";
import { addCard, ALL_QUESTS, countTownClears, getCards, hasAllCards, initProgress, missingQuests, onProgress, QUESTS, townClears, type Quest } from "./living/progress";
import { initSound, loop, sfx, stopAllLoops, stopLoop } from "./living/sound";
import { announce, closeDialog, initUi, say, type Option, type Speaker } from "./living/ui";

const CAT: Speaker = { name: "黑喵喵", portrait: "cat" };
const MERCHANT: Speaker = { name: "神祕商人", portrait: "merchant" };
const CARD_KEEPER: Speaker = { name: "翻牌攤老闆", portrait: "stand1" };
const SHEEP_KEEPER: Speaker = { name: "綿羊牆管理員", portrait: "stand2" };
const CRYPTO_KEEPER: Speaker = { name: "客棧掌櫃", portrait: "stand3" };
const OFFICE_KEEPER: Speaker = { name: "資安稽核員", portrait: "stand4" };
const SIGN: Speaker = { name: "告示牌" };
const TREE: Speaker = { name: "廣場聖誕樹" };
const PORTAL: Speaker = { name: "冰封的傳送門" };

const CLOSE: Option = { id: "bye", label: "先這樣" };

const layer = (name: string, visible: boolean) => {
  const path = `hs/${name}`;
  if (visible) {
    WA.room.showLayer(path);
  } else {
    WA.room.hideLayer(path);
  }
};

// ---------------------------------------------------- the world follows the player's progress

const QUEST_SPOTS: Record<string, Quest> = { stand1: "cardgame", stand2: "sheepwall", stand3: "cryptogame", stand4: "office", kahoot: "kahoot" };

const renderProgress = () => {
  const cards = getCards();
  for (const [spot, quest] of Object.entries(QUEST_SPOTS)) {
    const done = cards.includes(quest);
    layer(`${spot}_todo`, !done);
    layer(`${spot}_done`, done);
    if (spot !== "kahoot") {
      layer(`${spot}_lit`, done);
    }
  }

  const ready = hasAllCards();
  layer("merchant_locked", !ready);
  layer("merchant_ready", ready);
  layer("portal_sealed", !ready);
  layer("portal_open", ready);
  if (ready) {
    // Other players see the gold outline too.
    WA.player.setOutlineColor(255, 209, 102);
  }
};

const renderTree = () => {
  const clears = townClears();
  const tier = clears >= 15 ? 3 : clears >= 5 ? 2 : clears >= 1 ? 1 : 0;
  [1, 2, 3].forEach(n => layer(`tree${n}`, n === tier));
};

let fireworksTimer: ReturnType<typeof setTimeout> | undefined;
const celebrate = (seconds: number) => {
  sfx("all_clear", 0.6);
  layer("fireworks", true);
  clearTimeout(fireworksTimer);
  fireworksTimer = setTimeout(() => layer("fireworks", false), seconds * 1000);
};

const missingText = () => missingQuests().map(quest => QUESTS[quest].name).join("、");

const completeQuest = async (quest: Quest) => {
  const isNew = await addCard(quest);
  await countTownClears();
  const { name, reward } = QUESTS[quest];
  if (!isNew) {
    return;
  }
  sfx("card", 0.6);
  showToast("", `${name}完成！拿到了「${reward}」`);
  announce(`你通過了${name}`);
  if (hasAllCards()) {
    celebrate(8);
    announce(`🎉 ${ALL_QUESTS.length} 張卡集滿了！傳送門的冰融化了`);
  }
};

// ---------------------------------------------------- NPCs notice the player

const NEARBY: Record<string, { x: number; y: number; voice?: string }> = {
  cat: { x: 23, y: 29, voice: "talk_cat" },
  stand1: { x: 31, y: 28, voice: "talk_keeper" },
  stand2: { x: 39, y: 22, voice: "talk_keeper" },
  stand3: { x: 49, y: 22, voice: "talk_keeper" },
  stand4: { x: 57, y: 28, voice: "talk_keeper" },
  merchant: { x: 91, y: 41, voice: "talk_merchant" },
};
const lastGreeted = new Map<string, number>();

const noticePlayer = (x: number, y: number) => {
  for (const [name, npc] of Object.entries(NEARBY)) {
    const near = Math.hypot(x / 32 - npc.x - 0.5, y / 32 - npc.y - 0.5) < 4;
    layer(`${name}_near`, near);
    const now = Date.now();
    if (near && now - (lastGreeted.get(name) ?? 0) > 25000) {
      lastGreeted.set(name, now);
      if (npc.voice) {
        sfx(npc.voice, 0.3);
      }
    }
  }
};

let stepping: ReturnType<typeof setInterval> | undefined;
let stepCount = 0;
const setWalking = (moving: boolean) => {
  if (moving && !stepping) {
    stepping = setInterval(() => sfx(stepCount++ % 2 ? "step1" : "step2", 0.28), 300);
  } else if (!moving && stepping) {
    clearInterval(stepping);
    stepping = undefined;
  }
};

// ---------------------------------------------------- conversations

const leaveCloses = (area: string) => WA.room.area.onLeave(area).subscribe(closeDialog);

const timedQuest = (area: string, speaker: Speaker, quest: Quest, title: string, src: string, pitch: string, again: string) => {
  WA.room.area.onEnter(area).subscribe(async () => {
    sfx("talk_keeper", 0.35);
    const done = getCards().includes(quest);
    const choice = await say(speaker, done ? again : pitch, [
      { id: "play", label: done ? "再玩一次" : "我來試試" },
      CLOSE,
    ]);
    closeDialog();
    if (choice !== "play") {
      return;
    }

    const enterTime = Date.now();
    WA.ui.modal.openModal({ title, src, allow: "fullscreen", allowApi: false, position: "center" }, async () => {
      if (Date.now() - enterTime <= 30 * 1000) {
        sfx("wrong", 0.4);
        await say(speaker, "這麼快就走啦？至少待滿 30 秒才算數喔，再試一次吧！");
        return;
      }
      await completeQuest(quest);
      const reward = QUESTS[quest].reward;
      await say(speaker, `不錯嘛！這張「${reward}」是你的了。${hasAllCards() ? "快去找商人吧！" : `還剩：${missingText()}。`}`);
      await postState(`${quest}/finish`);
    });
  });
  leaveCloses(area);
};

const catChat = async () => {
  sfx("talk_cat", 0.45);
  const count = getCards().length;
  const opening =
    count === 0
      ? "こんにちにゃー！歡迎來到黑客社的虛擬世界"
      : hasAllCards()
      ? "喵！卡都集滿了！快去東南邊的森林找商人，順便看看融化的傳送門にゃ"
      : `已經有 ${count} 張卡了にゃ。還差：${missingText()}`;

  const choice = await say(CAT, opening, [
    { id: "what", label: "這裡可以幹嘛？" },
    { id: "who", label: "你誰啊？" },
    { id: "town", label: "鎮上最近怎樣？" },
  ]);

  if (choice === "who") {
    await say(CAT, "我是黑喵喵だにゃー");
  } else if (choice === "town") {
    const others = Array.from(WA.players.list()).length;
    const clears = townClears();
    await say(CAT, `現在還有 ${others} 個人在鎮上，大家總共破了 ${clears} 關。破得越多，廣場的聖誕樹就越亮にゃ`);
  } else if (choice === "what") {
    const next = await say(CAT, `聽說闖完 ${ALL_QUESTS.length} 個關卡，可以去找戴紫色帽子的神祕商人換禮物`, [
      { id: "hat", label: "紫色帽子？" },
      { id: "where", label: "他在哪裡？" },
    ]);
    if (next === "hat") {
      await say(CAT, "紫色，因為外星人不會戴帽子");
    } else if (next === "where") {
      await say(CAT, "... 你自己找吧");
    }
  }
};

const cryptoChat = async () => {
  sfx("talk_keeper", 0.35);
  const done = getCards().includes("cryptogame");
  const start = await say(CRYPTO_KEEPER, done ? "解密高手又來啦！要再挑戰一次嗎？" : "這裡是解密客棧，你今天密了嗎？來挑戰我的密碼吧！", [
    { id: "go", label: "開始" },
    CLOSE,
  ]);
  if (start !== "go") {
    return closeDialog();
  }

  for (const qa of cryptoData) {
    const picked = await say(
      CRYPTO_KEEPER,
      `[${qa.name}] 密文：${qa.cipher}　KEY：${qa.key}`,
      Object.values(qa.sel).map((label, index) => ({ id: String(index), label }))
    );
    if (picked === null) {
      return;
    }
    if (Number(picked) !== qa.ans) {
      sfx("wrong", 0.4);
      await say(CRYPTO_KEEPER, "嘿嘿，答錯了！再來一次吧。");
      return;
    }
    sfx("correct", 0.45);
  }

  await completeQuest("cryptogame");
  await say(CRYPTO_KEEPER, `全對！這張「${QUESTS.cryptogame.reward}」拿去。`);
  await postState("cryptogame/finish");
};

const merchantChat = async () => {
  sfx("talk_merchant", 0.45);
  const choice = await say(MERCHANT, hasAllCards() ? "早安人類。那些卡……我聞到了。" : "早安人類。", [
    { id: "who", label: "你是誰？" },
    { id: "redeem", label: "我要換禮物" },
  ]);

  if (choice === "who") {
    await say(MERCHANT, "我是...\n我忘記了...");
    return;
  }
  if (choice !== "redeem") {
    return;
  }
  if (!hasAllCards()) {
    await say(MERCHANT, `你的卡還不夠。還差：${missingText()}`);
    return;
  }

  say(MERCHANT, "(正在檢查你的遊戲進度...)");
  const [result] = await Promise.all([postState("redeem"), wait(1000)]);
  if (!result) {
    await say(MERCHANT, "今天的帳本打不開……等等再來吧。");
    return;
  }
  if (!result.success) {
    await say(MERCHANT, result.detail ?? "現在沒辦法兌換，等等再來吧。");
    return;
  }

  closeDialog();
  WA.ui.modal.openModal({
    title: "黑客社資安週RPG 兌獎問卷",
    src: result.url,
    allow: "fullscreen",
    allowApi: false,
    position: "center",
  });
};

const initConversations = () => {
  WA.room.area.onEnter("entrySign").subscribe(async () => {
    const choice = await say(SIGN, "4qyG77iP6Kej6KyO5bGL 4p6h77iP6IGW6KqV5buj5aC0", [{ id: "look", label: "仔細查看" }]);
    if (choice) {
      await say(SIGN, "(看不懂上面的字... 前面有個人，去問看看牠好了)");
    }
  });
  leaveCloses("entrySign");

  WA.room.area.onEnter("guideCat").subscribe(catChat);
  leaveCloses("guideCat");

  WA.room.area.onEnter("tree").subscribe(() => {
    const clears = townClears();
    say(TREE, clears ? `是聖誕樹ㄟ🎄 全鎮已經破了 ${clears} 關，它正為大家發光。` : "是聖誕樹ㄟ🎄 還沒有燈亮著，等第一個人破關吧。");
  });
  leaveCloses("tree");

  timedQuest(
    "stand1",
    CARD_KEEPER,
    "cardgame",
    "翻牌遊戲",
    "https://hackersir.org/2025isweek/",
    "來來來，翻牌遊戲！玩滿 30 秒再走才算過關喔。",
    "又回來啦？看來你真的喜歡翻牌。"
  );
  timedQuest(
    "stand2",
    SHEEP_KEEPER,
    "sheepwall",
    "腳捲綿羊牆",
    "https://docs.google.com/presentation/d/e/2PACX-1vRuyGFb0zrMgHUckZaFHJ_vTVmDifqu6vT9uVGTGe1CuBgmsVAAQHHYd9hPfb5lxQ/embed",
    "這面牆上都是沒注意資安的小綿羊。好好看 30 秒，別成為下一隻。",
    "牆上好像又多了幾隻綿羊，要再看看嗎？"
  );

  WA.room.area.onEnter("stand3").subscribe(cryptoChat);
  leaveCloses("stand3");

  WA.room.area.onEnter("stand4").subscribe(async () => {
    sfx("talk_keeper", 0.35);
    const best = Number(loadSaved("hsOfficeBest")) || 0;
    const choice = await say(
      OFFICE_KEEPER,
      best
        ? `你上次找到 ${best} 個問題。要再進辦公室挑戰一次嗎？`
        : "這間辦公室的資安習慣糟透了。給你兩分鐘，進去幫我找出至少 4 個問題，過關就給你一張「辦公室通行卡」。",
      [{ id: "go", label: "進辦公室" }, CLOSE]
    );
    closeDialog();
    if (choice === "go") {
      stopAllLoops();
      WA.nav.goToRoom("office.tmj");
    }
  });
  leaveCloses("stand4");

  WA.room.area.onEnter("merchant").subscribe(merchantChat);
  leaveCloses("merchant");

  WA.room.area.onEnter("hsPortalGate").subscribe(async () => {
    if (!hasAllCards()) {
      await say(PORTAL, `厚厚的冰封住了它。也許集滿所有卡就會融化。還差：${missingText()}`);
      return;
    }
    sfx("portal", 0.6);
    announce("傳送門把你送回了廣場");
    await wait(500);
    WA.nav.goToRoom("#hsFromPortal");
  });
  leaveCloses("hsPortalGate");
};

// ---------------------------------------------------- start

WA.onInit()
  .then(async () => {
    initSound();
    await initUi();
    loop("bgm_town", 0.22);
    loop("wind", 0.16);

    onProgress(renderProgress);
    await initProgress();
    await countTownClears();
    renderTree();
    WA.state.onVariableChange("townClears").subscribe(renderTree);

    await initPresence(() => celebrate(8));
    initConversations();

    WA.player.onPlayerMove(({ x, y, moving }) => {
      setWalking(moving);
      noticePlayer(x, y);
      stepInSnow(WA.player.playerId, x, y);
    });

    WA.room.area.onEnter("hsCampfire").subscribe(() => {
      loop("campfire", 0.35);
      announce("營火旁可以和靠近的人聊天");
    });
    WA.room.area.onLeave("hsCampfire").subscribe(() => stopLoop("campfire"));
    WA.room.area.onEnter("hsPlaza").subscribe(() => announce("廣場上可以和靠近的人聊天"));
  })
  .catch(e => console.error(e));

export {};
