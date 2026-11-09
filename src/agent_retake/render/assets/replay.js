const {timeline, theme, controls, size} = JSON.parse(document.querySelector("#data").textContent);
const root = document.documentElement;
const viewport = document.querySelector("#viewport");
const lines = document.querySelector("#lines");
const composer = document.querySelector("#composer");
const draft = document.querySelector("#draft");
const caret = document.querySelector("#caret");
const palette = {claude:"#eea986", codex:"#9bdacc", pi:"#c4adfb", grok:"#d0d8e8", ...theme.accents};
const glyphs = {claude:"❯", codex:"›", pi:"π", grok:"›", ...theme.glyphs};
const names = {claude:"Claude Code", codex:"Codex", pi:"pi", grok:"Grok Build"};
for (const [key, value] of Object.entries({fg:theme.foreground, bg:theme.background,
    pad:theme.padding+"px", font:theme.font, size:theme.size+"px"})) root.style.setProperty("--"+key, value);
document.querySelector("#title").textContent = timeline.title;

function appendHighlighted(node, value, highlights) {
    let rest = value;
    while (rest) {
        const matches = highlights.filter(h => h && rest.includes(h))
            .sort((a,b) => rest.indexOf(a)-rest.indexOf(b) || b.length-a.length);
        if (!matches.length) { node.append(rest); break; }
        const match = matches[0], offset = rest.indexOf(match);
        node.append(rest.slice(0,offset));
        const mark = document.createElement("mark");
        mark.textContent = match;
        node.append(mark);
        rest = rest.slice(offset+match.length);
    }
}

function messageLine(shot, value) {
    const item = document.createElement("div");
    item.className = "line " + shot.role + "-message";
    item.style.setProperty("--accent", palette[shot.harness]);
    const speaker = document.createElement("span");
    speaker.className = "speaker";
    speaker.textContent = {user:"You", assistant:names[shot.harness], tool:"Tool"}[shot.role];
    const body = document.createElement("span");
    body.className = "message-text";
    appendHighlighted(body, value, shot.highlights);
    item.append(speaker, body);
    return item;
}

const historyLines = document.querySelector("#history");
for (const shot of timeline.history) {
    historyLines.append(messageLine(shot, shot.text));
}

function seek(time) {
    const t = Math.min(timeline.duration, Math.max(0, Number(time)));
    lines.replaceChildren();
    draft.replaceChildren();
    caret.hidden = true;
    let active = timeline.shots[0].shot.harness;
    const latestPrompt = timeline.shots.findLast(entry => entry.shot.role === "user" && entry.start <= t);
    for (const {shot,start,end} of timeline.shots) {
        if (t < start) break;
        active = shot.harness;
        const pct = Math.min(1,(t-start)/(end-start));
        let value = shot.text;
        if (shot.mode === "typed" && t < end) {
            const chars = Array.from(value);
            appendHighlighted(draft, chars.slice(0,Math.ceil(chars.length*pct)).join(""), shot.highlights);
            caret.hidden = false;
            break;
        }
        if (t === start) break;
        if (shot.mode === "burst" || shot.mode === "condensed") {
            const rows = value.split("\n");
            value = rows.slice(0,Math.ceil(rows.length*pct)).join("\n");
        } else if (shot.mode !== "still") {
            const chars = Array.from(value);
            value = chars.slice(0,Math.floor(chars.length*pct)).join("");
        }
        const item = messageLine(shot, value);
        if (latestPrompt && start < latestPrompt.start) item.classList.add("earlier");
        lines.append(item);
    }
    document.querySelector("#harness").textContent = glyphs[active] + " " + names[active];
    root.style.setProperty("--accent",palette[active]);
    viewport.scrollTop = viewport.scrollHeight;
    composer.scrollTop = composer.scrollHeight;
    document.querySelector("#seconds").textContent = t.toFixed(2) + " s";
    document.querySelector("#time").value = t;
}
window.seek = seek;
const slider = document.querySelector("#time");
slider.max = timeline.duration;
slider.oninput = () => seek(slider.value);
document.querySelector("#controls").hidden = !controls;
const stage = document.querySelector("#stage");
stage.style.width = size.width+"px";
stage.style.height = size.height+"px";
stage.style.setProperty("--margin", Math.min(32,Math.max(8,size.width*0.02))+"px");
stage.style.setProperty("--radius", Math.min(20,Math.max(8,size.width*0.01))+"px");
if (controls) {
    const fit = () => {
        const height = innerHeight-document.querySelector("#controls").offsetHeight;
        stage.style.transform = "scale("+Math.min(innerWidth/size.width,height/size.height)+")";
    };
    fit();
    window.addEventListener("resize",fit);
}
seek(0);
