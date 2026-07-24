(function () {
  function initChat({ pollUrl, sendUrl }) {
    const messagesEl = document.getElementById("chat-messages");
    const formEl = document.getElementById("chat-form");
    const inputEl = document.getElementById("chat-input");
    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

    let lastId = parseInt(messagesEl.dataset.lastId || "0", 10);
    let inFlight = false;
    const renderedIds = new Set(); // 같은 메시지가 두 번 그려지는 것을 막는다(전송 응답 + 폴링이 같은 메시지를 각자 가져올 수 있음)

    function appendMessage(msg) {
      if (renderedIds.has(msg.id)) return; // 이미 그린 메시지면 무시
      renderedIds.add(msg.id);

      const row = document.createElement("div");
      row.className = "chat-bubble-row " + (msg.is_mine ? "mine" : "theirs");

      const bubble = document.createElement("div");
      bubble.className = "chat-bubble";

      if (!msg.is_mine) {
        const nameEl = document.createElement("div");
        nameEl.className = "chat-sender";
        nameEl.textContent = msg.sender_nickname; // textContent만 사용 -> 스크립트로 해석되지 않음 (XSS 방지)
        bubble.appendChild(nameEl);
      }

      const contentEl = document.createElement("div");
      contentEl.className = "chat-content";
      contentEl.textContent = msg.content; // innerHTML을 쓰지 않는다 - DOM 기반 XSS 원천 차단

      const timeEl = document.createElement("div");
      timeEl.className = "chat-time";
      timeEl.textContent = msg.created_at;

      bubble.appendChild(contentEl);
      bubble.appendChild(timeEl);
      row.appendChild(bubble);
      messagesEl.appendChild(row);
      messagesEl.scrollTop = messagesEl.scrollHeight;

      if (msg.id > lastId) lastId = msg.id;
    }

    async function poll() {
      try {
        const res = await fetch(pollUrl + "?after_id=" + lastId);
        if (res.ok) {
          const data = await res.json();
          (data.messages || []).forEach(appendMessage);
          // 서버가 보내주는 last_id는 화면에 표시되지 않은(차단된 사용자) 메시지까지 반영한 커서다.
          // 이 값을 반영하지 않으면 차단한 사용자의 메시지가 새로 올 때마다 같은 구간을 계속 재조회하게 된다.
          if (typeof data.last_id === "number" && data.last_id > lastId) {
            lastId = data.last_id;
          }
        }
      } catch (e) {
        // 네트워크 오류 시 잠깐 쉬었다가 재시도한다
        await new Promise((r) => setTimeout(r, 2000));
      }
      poll();
    }

    formEl.addEventListener("submit", async function (e) {
      e.preventDefault();
      if (inFlight) return;

      const content = inputEl.value.trim();
      if (!content) return;

      inFlight = true;
      inputEl.disabled = true;

      try {
        const res = await fetch(sendUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({ content: content }),
        });
        const data = await res.json();
        if (res.ok && data.message) {
          inputEl.value = "";
          appendMessage(data.message);
        } else {
          alert(data.error || "메시지 전송에 실패했습니다.");
        }
      } catch (e) {
        alert("네트워크 오류로 메시지를 보내지 못했습니다.");
      } finally {
        inFlight = false;
        inputEl.disabled = false;
        inputEl.focus();
      }
    });

    poll();
  }

  window.TinyChat = { initChat: initChat };

  document.addEventListener("DOMContentLoaded", function () {
    const root = document.getElementById("chat-messages");
    if (!root) return;
    if (root.dataset.chatInitialized === "true") return; // 같은 페이지에서 초기화가 두 번 일어나는 것 방지
    root.dataset.chatInitialized = "true";

    const pollUrl = root.dataset.pollUrl;
    const sendUrl = root.dataset.sendUrl;
    if (pollUrl && sendUrl) {
      initChat({ pollUrl: pollUrl, sendUrl: sendUrl });
    }
  });
})();
