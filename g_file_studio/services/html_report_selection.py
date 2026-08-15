from __future__ import annotations


def selection_style() -> str:
    """Shared HTML report styles for row selection used only for visual review."""
    return (
        ".report-select-col{width:46px;min-width:46px;text-align:center!important;position:sticky;left:0;z-index:3;}"
        "th.report-select-col{background:#dce9e4!important;}"
        "td.report-select-col{background:inherit;}"
        ".report-select{width:17px;height:17px;cursor:pointer;vertical-align:middle;}"
        "tr.report-row-selected td{outline:2px solid rgba(37,99,235,.35);outline-offset:-2px;}"
        "tr.report-row-selected td:not(.report-select-col){box-shadow:inset 0 0 0 9999px rgba(59,130,246,.10);}"
        ".report-selection-bar{display:flex;align-items:center;gap:12px;margin:10px 0;color:#475569;font-size:13px;}"
        ".report-selection-count{font-weight:600;color:#1d4ed8;}"
    )


def selection_bar() -> str:
    return (
        '<div class="report-selection-bar">'
        '<span>查看辅助：可单选/多选行，勾选后整行高亮。</span>'
        '<span class="report-selection-count" id="reportSelectionCount">已选择 0 行</span>'
        '</div>'
    )


def selection_header() -> str:
    return (
        '<th class="report-select-col" title="全选/取消全选">'
        '<input id="reportSelectAll" class="report-select" type="checkbox" aria-label="全选">'
        '</th>'
    )


def selection_cell() -> str:
    return (
        '<td class="report-select-col">'
        '<input class="report-select report-row-select" type="checkbox" aria-label="选择此行">'
        '</td>'
    )


def selection_script() -> str:
    return r'''<script>
(function(){
  function updateCount(){
    var checked=document.querySelectorAll('.report-row-select:checked').length;
    var label=document.getElementById('reportSelectionCount');
    if(label){label.textContent='已选择 '+checked+' 行';}
    var all=document.getElementById('reportSelectAll');
    var boxes=Array.from(document.querySelectorAll('.report-row-select'));
    if(all){
      all.checked=boxes.length>0 && checked===boxes.length;
      all.indeterminate=checked>0 && checked<boxes.length;
    }
  }
  function setRowState(box){
    var row=box.closest('tr');
    if(row){row.classList.toggle('report-row-selected', box.checked);}
  }
  document.querySelectorAll('.report-row-select').forEach(function(box){
    box.addEventListener('change', function(){setRowState(box);updateCount();});
  });
  var all=document.getElementById('reportSelectAll');
  if(all){
    all.addEventListener('change', function(){
      document.querySelectorAll('.report-row-select').forEach(function(box){
        box.checked=all.checked; setRowState(box);
      });
      updateCount();
    });
  }
  updateCount();
})();
</script>'''
