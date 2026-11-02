// Tells the server the browser's time zone, so it shows times in it: writes the IANA name, such as
// Europe/Kyiv, to the `sc_time_zone` cookie when it is missing or different. It sends nothing,
// stores nothing else and reloads nothing; the next page uses the zone. Without it, every time is
// shown in UTC, labelled so (specs/012.1-teacher-competitions research R5, contracts/components.md
// §7).

const COOKIE = "sc_time_zone";
const NAME = /^[A-Za-z0-9_+\-]+(?:\/[A-Za-z0-9_+\-]+)*$/;

const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;

if (typeof zone === "string" && zone.length <= 64 && NAME.test(zone)) {
  const current = document.cookie
    .split("; ")
    .find((pair) => pair.startsWith(COOKIE + "="));
  if (current !== COOKIE + "=" + zone) {
    const secure = location.protocol === "https:" ? "; Secure" : "";
    document.cookie = COOKIE + "=" + zone + "; Path=/; Max-Age=31536000; SameSite=Lax" + secure;
  }
}
