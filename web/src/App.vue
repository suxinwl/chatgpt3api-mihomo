<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from "vue";

const logged = ref(false),
  loading = ref(true),
  busy = ref(false);
const error = ref(""),
  notice = ref(""),
  overview = ref(null),
  dialog = ref(false);
const loginForm = ref({ username: "admin", password: "" });
const form = ref({ name: "", url: "", content: "", interval: 24 });
const editing = ref(null),
  importMode = ref(false),
  delays = ref({}),
  testing = ref({});
let timer, previousFocus;
const modal = ref(null);
watch(dialog, async (visible) => {
  if (visible) {
    previousFocus = document.activeElement;
    await nextTick();
    modal.value?.querySelector("input")?.focus();
  } else {
    await nextTick();
    previousFocus?.focus();
    if (logged.value)
      refresh().catch((e) => {
        error.value = e.message;
      });
  }
});
function trapFocus(event) {
  if (event.key === "Escape") {
    if (!busy.value) dialog.value = false;
    return;
  }
  if (event.key !== "Tab") return;
  const elements = [
    ...modal.value.querySelectorAll(
      "button:not(:disabled),input:not(:disabled),textarea:not(:disabled)",
    ),
  ];
  const first = elements[0],
    last = elements.at(-1);
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

async function api(path, method = "GET", payload) {
  const response = await fetch("/api" + path, {
    method,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-Manager-Request": "1" },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  const body = await response.json().catch(() => null);
  if (response.status === 401) logged.value = false;
  if (!response.ok) {
    const failure = new Error(
      typeof body?.detail === "string"
        ? body.detail
        : "输入不符合要求，请检查后重试",
    );
    failure.status = response.status;
    throw failure;
  }
  return body;
}
function checkedOverview(value) {
  if (
    !value ||
    typeof value.core_running !== "boolean" ||
    !Array.isArray(value.profiles) ||
    !Array.isArray(value.nodes) ||
    !value.profiles.every(
      (p) =>
        typeof p.id === "string" &&
        typeof p.name === "string" &&
        typeof p.active === "boolean" &&
        typeof p.actions?.activate === "boolean" &&
        typeof p.actions?.refresh === "boolean" &&
        typeof p.actions?.delete === "boolean",
    ) ||
    !value.nodes.every(
      (n) => typeof n.name === "string" && typeof n.selected === "boolean",
    )
  )
    throw new Error("服务返回的数据不完整，请刷新重试");
  return value;
}
async function refresh() {
  const data = checkedOverview(await api("/overview"));
  overview.value = data;
  logged.value = true;
}
async function action(callback, message) {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  notice.value = "";
  try {
    const result = await callback();
    await refresh();
    notice.value = result?.message || message;
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function login() {
  await action(async () => {
    await api("/login", "POST", loginForm.value);
    loginForm.value.password = "";
  }, "登录成功");
}
async function logout() {
  try {
    await api("/logout", "POST");
  } catch (e) {
    error.value = e.message;
    return;
  }
  logged.value = false;
  overview.value = null;
  error.value = "";
  notice.value = "";
  dialog.value = false;
}
function open(profile = null) {
  editing.value = profile?.id || null;
  importMode.value = !profile?.remote && !!profile;
  form.value = {
    name: profile?.name || "",
    url: "",
    content: "",
    interval: profile?.interval ?? 24,
  };
  dialog.value = true;
}
async function readFile(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  if (file.size > 8 * 1024 * 1024) {
    error.value = "配置文件不能超过 8 MB";
    return;
  }
  form.value.content = await file.text();
  if (!form.value.name) form.value.name = file.name.replace(/\.ya?ml$/i, "");
}
async function save() {
  await action(
    async () => {
      const payload = {
        ...form.value,
        url: importMode.value && !editing.value ? "" : form.value.url,
        content: !importMode.value || editing.value ? "" : form.value.content,
      };
      const result = await api(
        editing.value ? "/profiles/" + editing.value : "/profiles",
        editing.value ? "PUT" : "POST",
        payload,
      );
      dialog.value = false;
      form.value.content = "";
      form.value.url = "";
      return result;
    },
    editing.value ? "订阅已保存" : "订阅已添加；第一个订阅自动启用",
  );
}
async function remove(profile) {
  if (!window.confirm(`删除订阅“${profile.name}”？`)) return;
  await action(() => api("/profiles/" + profile.id, "DELETE"), "订阅已删除");
}
async function delay(node) {
  if (testing.value[node.name]) return;
  testing.value[node.name] = true;
  try {
    const result = await api("/nodes/delay", "POST", { name: node.name });
    delays.value[node.name] = result.delay;
  } catch (e) {
    delays.value[node.name] = 0;
    error.value = e.message;
  } finally {
    testing.value[node.name] = false;
  }
}
async function testAll() {
  for (const node of overview.value?.nodes || []) {
    if (!logged.value) break;
    await delay(node);
  }
}
function delayLabel(node) {
  const value = delays.value[node.name] ?? node.delay;
  return value == null ? "未测速" : value === 0 ? "不可用" : value + " ms";
}
function timeLabel(value) {
  return new Date(value * 1000).toLocaleString();
}
onMounted(async () => {
  try {
    await refresh();
  } catch (e) {
    if (e.status !== 401) error.value = e.message;
  } finally {
    loading.value = false;
  }
  timer = setInterval(async () => {
    if (
      document.visibilityState === "visible" &&
      logged.value &&
      !busy.value &&
      !dialog.value
    ) {
      try {
        await refresh();
      } catch (e) {
        error.value = e.message;
      }
    }
  }, 30000);
});
onUnmounted(() => clearInterval(timer));
</script>

<template>
  <main>
    <header class="header">
      <div class="brand">
        <span class="mark" aria-hidden="true">M</span>
        <div>
          <h1>Mihomo</h1>
          <p>订阅与代理管理</p>
        </div>
      </div>
      <div v-if="logged" class="header-right">
        <span class="status" :class="{ offline: !overview?.core_running }">{{
          overview?.core_running ? "内核运行中" : "内核离线"
        }}</span
        ><button class="quiet" @click="logout">退出登录</button>
      </div>
    </header>
    <div v-if="error && !dialog" class="message error" role="alert">
      {{ error
      }}<button aria-label="关闭错误提示" @click="error = ''">×</button>
    </div>
    <div v-if="notice" class="message success" role="status">
      {{ notice }}<button aria-label="关闭提示" @click="notice = ''">×</button>
    </div>
    <p v-if="loading" class="muted">正在连接管理后台…</p>
    <section v-else-if="!logged" class="login panel">
      <span class="eyebrow">CONTROL PANEL</span>
      <h2>登录管理后台</h2>
      <p class="muted">管理订阅、切换出口和检查节点连接。</p>
      <form @submit.prevent="login">
        <label
          >用户名<input
            v-model="loginForm.username"
            autocomplete="username"
            required
            maxlength="128" /></label
        ><label
          >密码<input
            v-model="loginForm.password"
            type="password"
            autocomplete="current-password"
            required
            maxlength="1024" /></label
        ><button class="primary" :disabled="busy">
          {{ busy ? "正在登录…" : "登录" }}
        </button>
      </form>
    </section>
    <template v-else>
      <section class="summary">
        <div>
          <span class="eyebrow">当前出口</span>
          <h2>{{ overview?.selected || "等待添加订阅" }}</h2>
          <p class="muted">
            {{
              overview?.profiles.find((p) => p.active)?.name ||
              "添加订阅链接，或导入节点配置。"
            }}
          </p>
        </div>
        <div class="versions">
          <span>管理后台 {{ overview?.version }}</span
          ><span>Mihomo {{ overview?.core_version || "—" }}</span>
        </div>
      </section>
      <section class="panel">
        <div class="section-heading">
          <div>
            <h2>
              订阅管理
              <span class="count">{{ overview?.profiles.length || 0 }}</span>
            </h2>
            <p class="muted">订阅单独保存，选择一个作为当前出口。</p>
          </div>
          <button class="primary" :disabled="busy" @click="open()">
            ＋ 添加订阅
          </button>
        </div>
        <div v-if="!overview?.profiles.length" class="empty">
          还没有订阅。添加链接或导入节点配置后即可选择节点。
        </div>
        <div
          v-for="profile in overview?.profiles"
          :key="profile.id"
          class="profile"
        >
          <div class="profile-info">
            <div class="profile-title">
              <h3>{{ profile.name }}</h3>
              <span v-if="profile.active" class="tag">使用中</span>
            </div>
            <p>
              {{ profile.source }} · {{ profile.count }} 个节点 ·
              {{
                profile.interval ? profile.interval + " 小时更新" : "手动更新"
              }}
            </p>
            <p class="muted">最近更新 {{ timeLabel(profile.updated) }}</p>
            <p v-if="profile.error" class="inline-error">{{ profile.error }}</p>
          </div>
          <div class="actions">
            <button
              :disabled="busy || !profile.actions.activate"
              @click="
                action(
                  () => api('/profiles/' + profile.id + '/activate', 'POST'),
                  '订阅已切换',
                );
                delays = {};
              "
            >
              {{ profile.active ? "已启用" : "切换" }}</button
            ><button
              v-if="profile.actions.refresh"
              :disabled="busy"
              @click="
                action(
                  () => api('/profiles/' + profile.id + '/refresh', 'POST'),
                  '订阅已更新',
                )
              "
            >
              更新</button
            ><button :disabled="busy" @click="open(profile)">编辑</button
            ><button
              class="danger"
              :disabled="busy || !profile.actions.delete"
              @click="remove(profile)"
            >
              删除
            </button>
          </div>
        </div>
      </section>
      <section class="panel">
        <div class="section-heading">
          <div>
            <h2>
              节点选择
              <span class="count">{{ overview?.nodes.length || 0 }}</span>
            </h2>
            <p class="muted">Auto 自动选择延迟较低的节点。</p>
          </div>
          <button
            :disabled="
              busy ||
              !overview?.nodes.length ||
              Object.values(testing).some(Boolean)
            "
            @click="testAll"
          >
            全部测速
          </button>
        </div>
        <div v-if="!overview?.nodes.length" class="empty">
          启用订阅后，节点会显示在这里。
        </div>
        <div class="nodes">
          <article
            v-for="node in overview?.nodes"
            :key="node.name"
            class="node"
            :class="{ selected: node.selected }"
          >
            <div class="node-title">
              <h3>{{ node.name }}</h3>
              <span v-if="node.selected" class="tag">当前</span>
            </div>
            <p class="muted">{{ node.type }}</p>
            <div class="node-bottom">
              <button
                class="delay"
                :disabled="testing[node.name]"
                @click="delay(node)"
              >
                {{ testing[node.name] ? "测速中…" : delayLabel(node) }}</button
              ><button
                :disabled="busy || node.selected"
                @click="
                  action(
                    () => api('/nodes/selected', 'PUT', { name: node.name }),
                    '出口节点已切换',
                  )
                "
              >
                {{ node.selected ? "已选择" : "选择" }}
              </button>
            </div>
          </article>
        </div>
      </section>
    </template>
    <footer>chatgpt3api-mihomo · 订阅配置保存在服务器数据卷中</footer>
    <div v-if="dialog" class="backdrop" @click.self="!busy && (dialog = false)">
      <section
        ref="modal"
        class="modal panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="form-title"
        @keydown="trapFocus"
      >
        <div class="section-heading">
          <h2 id="form-title">{{ editing ? "编辑订阅" : "添加订阅" }}</h2>
          <button
            :disabled="busy"
            aria-label="关闭订阅表单"
            @click="dialog = false"
          >
            ×
          </button>
        </div>
        <div v-if="error" class="message error" role="alert">{{ error }}</div>
        <form @submit.prevent="save">
          <label
            >订阅名称<input
              v-model="form.name"
              required
              maxlength="80"
              autofocus
          /></label>
          <div v-if="!editing" class="tabs">
            <button
              type="button"
              :class="{ active: !importMode }"
              @click="importMode = false"
            >
              订阅链接</button
            ><button
              type="button"
              :class="{ active: importMode }"
              @click="importMode = true"
            >
              导入配置
            </button>
          </div>
          <template v-if="!importMode"
            ><label
              >{{
                editing
                  ? "新订阅链接（留空保留原链接）"
                  : "订阅链接（Clash / Mihomo 或 VLESS Base64）"
              }}<input
                v-model="form.url"
                type="url"
                :required="!editing"
                placeholder="https://…"
                autocomplete="off" /></label
            ><label
              >自动更新间隔（小时，0 表示关闭）<input
                v-model.number="form.interval"
                type="number"
                min="0"
                max="720"
                required /></label></template
          ><template v-else-if="!editing"
            ><label
              >选择配置文件<input
                type="file"
                accept=".yaml,.yml,.json,.txt"
                @change="readFile" /></label
            ><label
              >或粘贴配置 / VLESS 链接 / Base64 订阅<textarea
                v-model="form.content"
                rows="8"
                required
                placeholder="proxies:&#10;  …"
                spellcheck="false"
              ></textarea>
            </label>
            <p class="muted">
              支持 Clash/Mihomo 配置、VLESS 链接和 Base64 订阅。
              VLESS 链接支持 TCP、WS、gRPC 与 TLS/Reality；配置中的其他协议由内核校验。
            </p></template
          >
          <p v-else class="muted">
            本地配置可以改名。修改节点时，请导入新配置后切换。
          </p>
          <div class="form-actions">
            <button type="button" :disabled="busy" @click="dialog = false">
              取消</button
            ><button class="primary" :disabled="busy">
              {{ busy ? "正在校验并保存…" : "保存" }}
            </button>
          </div>
        </form>
      </section>
    </div>
  </main>
</template>
