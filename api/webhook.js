import axios from "axios";

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).send("Method Not Allowed");
  }

  const TOKEN = "8337510534:AAH6fXGNshjAoW5Bur_j5X-tg3xN8TkvhOs";

  const BB_WEBHOOK = `https://api.bots.business/tg_webhooks/${TOKEN}`;

  try {
    const update = req.body;

    // 🔍 Log incoming update
    console.log("Incoming:", update);

    // 🛡️ Optional filter example
    if (update.message && update.message.text?.includes("spam")) {
      return res.status(200).send("Blocked");
    }

    // 🔁 Forward to Bots.Business
    await axios.post(BB_WEBHOOK, update);

    return res.status(200).send("OK");
  } catch (err) {
    console.error(err);
    return res.status(500).send("Error");
  }
}
