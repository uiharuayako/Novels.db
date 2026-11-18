%include('header', title=' / 文件浏览')
<link rel="stylesheet" href="{{app_url('/static/files.css')}}?v=1">
<main id="main-content" tabindex="-1" class="app-main files-page" data-file-browser data-api="{{app_url('/api/files')}}" data-page-url="{{app_url('/files')}}" data-initial-path="{{initial_path}}">
  <header class="app-hero">
    <h1>文件浏览</h1>
  </header>
  <nav class="files-breadcrumbs" aria-label="文件夹路径"></nav>
  <section class="files-panel" aria-labelledby="files-heading">
    <div class="files-toolbar">
      <h2 id="files-heading">文库根目录</h2>
      <div class="files-actions"><a class="app-button app-button-secondary" data-files-parent hidden>返回上级</a><button class="app-button app-button-secondary" type="button" data-files-refresh>重新加载目录</button></div>
    </div>
    <p class="files-hint">按文件系统顺序分批显示，每批最多检查 100 项。翻页替换当前列表，重新加载回到目录开头。</p>
    <p class="files-status" role="status" aria-live="polite">正在加载…</p>
    <button type="button" class="app-button app-button-secondary" data-files-retry hidden>重试</button>
    <ul class="files-list" aria-label="文件和文件夹"></ul>
    <div class="files-pagination"><span data-files-count></span><button type="button" class="app-button" data-files-next hidden>下一页 <span aria-hidden="true">→</span></button></div>
    <noscript><p>请启用 JavaScript 以按需加载文件列表。</p></noscript>
  </section>
</main>
<script defer src="{{app_url('/static/files.js')}}?v=2"></script>
%include('footer')
