/// <reference types="@workadventure/iframe-api-typings" />

import data from "./kahoot_data.json";
import { type Popup } from "@workadventure/iframe-api-typings";
import { postState, wait } from "./utils";
import { addCard, initProgress, QUESTS } from "./living/progress";
import { initSound, loop, sfx, stopAllLoops } from "./living/sound";
import { closeDialog, initUi, say, setOnline, type Speaker } from "./living/ui";

const HOST: Speaker = { name: "解謎屋主持人" };
const ROUNDS = 3;
// How long the result stays on screen before the player is sent out.
const LEAVE_DELAY = 3500;

// Each area is subscribed to exactly once for the whole visit. Unsubscribing and subscribing
// again between questions makes WorkAdventure drop the new subscription, which froze the room
// after the first answer. The handlers read whichever question is current instead.
let current: { question: (typeof data)[number]; resolve: (correct: boolean) => void } | null = null;
let questionPopup: Popup | undefined;
const answerPopups: (Popup | undefined)[] = [];

const closeAll = () => {
  questionPopup?.close();
  questionPopup = undefined;
  answerPopups.forEach(popup => popup?.close());
  answerPopups.length = 0;
};

const listenToAreas = () => {
  WA.room.area.onEnter("question").subscribe(() => {
    closeDialog();
    if (current) {
      questionPopup?.close();
      questionPopup = WA.ui.openPopup("questionPopup", current.question.q, []);
    }
  });
  WA.room.area.onLeave("question").subscribe(() => {
    questionPopup?.close();
    questionPopup = undefined;
  });

  for (let index = 0; index < 4; index++) {
    WA.room.area.onEnter(`ans${index + 1}Show`).subscribe(() => {
      const answer = current?.question.sel[index];
      if (answer) {
        answerPopups[index]?.close();
        answerPopups[index] = WA.ui.openPopup(`ans${index + 1}Popup`, answer, []);
      }
    });
    WA.room.area.onLeave(`ans${index + 1}Show`).subscribe(() => {
      answerPopups[index]?.close();
      answerPopups[index] = undefined;
    });
    WA.room.area.onEnter(`ans${index + 1}`).subscribe(() => {
      if (!current || !current.question.sel[index]) {
        return;
      }
      const { question, resolve } = current;
      current = null;
      closeAll();
      resolve(question.ans === index + 1);
    });
  }
};

const showQuestion = (questionIndex: number) =>
  new Promise<boolean>(resolve => {
    closeAll();
    current = { question: data[questionIndex], resolve };
  });

// Waiting for the API to be ready
WA.onInit()
  .then(async () => {
    initSound();
    loop("bgm_kahoot", 0.2);

    await initUi();
    await WA.players.configureTracking({ players: true, movement: false });
    const refreshCount = () => setOnline(Array.from(WA.players.list()).length + 1);
    refreshCount();
    WA.players.onPlayerEnters.subscribe(refreshCount);
    WA.players.onPlayerLeaves.subscribe(refreshCount);
    listenToAreas();
    const state = await initProgress();

    const correctAns: number[] = state.kahoot_corrects || [];
    const kickCount: number = state.kahoot_kick_count || 0;

    for (let i = 0; i < ROUNDS; i++) {
      if (correctAns.length === data.length) {
        correctAns.length = 0;
      }

      let randomIndex = Math.floor(Math.random() * data.length);
      while (correctAns.includes(randomIndex)) {
        randomIndex = Math.floor(Math.random() * data.length);
      }

      const result = await showQuestion(randomIndex);

      if (result) {
        correctAns.push(randomIndex);
        sfx("correct", 0.5);
        if (i < ROUNDS - 1) {
          say(HOST, `答對了！還剩 ${ROUNDS - 1 - i} 題，回到起點準備下一題。`);
          // teleport to start
          WA.nav.goToRoom("kahoot_room.tmj");
        }
      } else {
        sfx("wrong", 0.5);
        const question = data[randomIndex];
        const toJail = kickCount + 1 >= 5;
        say(
          HOST,
          `答錯了！正確答案是「${question.sel[question.ans - 1]}」。挑戰失敗，` +
            (toJail ? "而且你被踢太多次了……準備去監獄冷靜一下。" : "要從第一題重新開始，先送你回小鎮。")
        );

        // kick player, after there has been time to read why
        await Promise.all([postState("kahoot/kick", { question: randomIndex }), wait(LEAVE_DELAY)]);
        stopAllLoops();
        return WA.nav.goToRoom(toJail ? "jail.tmj" : "map.tmj#from-kahoot_room");
      }
    }

    await addCard("kahoot");
    sfx("card", 0.6);
    say(HOST, `${ROUNDS} 題全對！拿到了「${QUESTS.kahoot.reward}」，馬上送你回小鎮。`);
    await Promise.all([postState("kahoot/finish", { corrects: correctAns }), wait(LEAVE_DELAY)]);
    stopAllLoops();
    WA.nav.goToRoom("map.tmj#from-kahoot_room");
  })
  .catch(e => console.error(e));

export {};
