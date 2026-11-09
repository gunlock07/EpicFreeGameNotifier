
const token = process.env.DISCORD_BOT_TOKEN;
const id = process.env.DISCORD_APPLICATION_ID;

if (!token || !id) {
  console.error("Discordの認証情報が設定されていません");
  process.exit(1);
}

const base = {
  type: 1,
  integration_types: [0],
  contexts: [0]
};

const commands = [
  {
    ...base,
    name: "無料ゲーム",
    description: "現在Epic Gamesで無料配布中のゲームを表示"
  },
  {
    ...base,
    name: "次回配布",
    description: "次回の無料配布予定を画像付きで表示"
  },
  {
    ...base,
    name: "ヘルプ",
    description: "BOTの使い方を表示"
  },
  {
    ...base,
    name: "通知設定",
    description: "定期通知を送るチャンネルを設定（管理者）",
    default_member_permissions: "32",
    options: [
      {
        type: 7,
        name: "チャンネル",
        description: "通知先のテキストチャンネル",
        required: true,
        channel_types: [0]
      }
    ]
  },
  {
    ...base,
    name: "通知停止",
    description: "このサーバーでの定期通知を停止（管理者）",
    default_member_permissions: "32"
  },
  {
    ...base,
    name: "通知状態",
    description: "現在の通知先設定を確認"
  }
];

const response = await fetch(
  `https://discord.com/api/v10/applications/${id}/commands`,
  {
    method: "PUT",
    headers: {
      authorization: `Bot ${token}`,
      "content-type": "application/json"
    },
    body: JSON.stringify(commands)
  }
);

const result = await response.json();

if (!response.ok) {
  console.error(
    "Discord registration failed:",
    response.status,
    JSON.stringify(result).slice(0, 600)
  );
  process.exit(1);
}

console.log(
  "Registered global commands:",
  result.map(x => x.name).join(", ")
);
