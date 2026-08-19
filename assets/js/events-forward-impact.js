(function () {
  "use strict";
  if (!/events\.html$/.test(location.pathname)) return;

  function deltaValue(value) {
    var m = String(value || "").replace(/,/g, "").match(/^([+-]?\d+(?:\.\d+)?)/);
    return m ? Number(m[1]) : null;
  }

  function correctedJudgement(record) {
    var title = String(record.event_name || "").toLowerCase();
    var delta = deltaValue(record.surprise);
    var inverse = ["失業率", "失業保険", "失業申請", "失業給付", "unemployment rate", "jobless claims", "unemployment claims", "claimant count"].some(function (word) {
      return title.indexOf(word) >= 0;
    });
    if (!inverse || delta === null || delta === 0) return record.result_judgement || "判定不能";
    return (delta > 0 ? "上振れ" : "下振れ") + "（雇用" + (delta > 0 ? "弱" : "強") + "）";
  }

  function marketContext(country) {
    if (country === "米国") return {rate:"米2年・10年債利回り", fx:"ドル・USD/JPY", stock:"米株"};
    if (country === "日本") return {rate:"日本国債利回り", fx:"円・USD/JPY", stock:"日経225先物・日本株"};
    if (country === "英国") return {rate:"英国債利回り", fx:"ポンド", stock:"英国株"};
    if (country === "欧州" || country === "ユーロ圏") return {rate:"欧州国債利回り", fx:"ユーロ・EUR/USD", stock:"欧州株"};
    return {rate:"対象国の国債利回り", fx:"対象国通貨", stock:"対象国株式"};
  }

  function forwardImpact(record) {
    var title = String(record.event_name || "").toLowerCase();
    var delta = deltaValue(record.surprise);
    var judgement = correctedJudgement(record);
    var c = marketContext(record.country);

    if (["fomc", "frb", "fed ", "日銀", "日銀関連", "boj", "ecb", "ecb関連", "発言"].some(function (word) { return title.indexOf(word) >= 0; })) {
      return {
        summary:"発言が政策金利見通しを変えたかが翌日への影響を決める。タカ派なら金利・通貨高、ハト派なら金利・通貨安が基本線。",
        continueIf:c.rate + "と" + c.fx + "が翌営業日も発言方向へ追随し、政策金利の織り込みが変化する。",
        changeIf:"従来見解の繰り返しにとどまり、金利市場の政策織り込みが変わらない。"
      };
    }

    if (["国債入札", "bond auction", "note auction", "treasury auction", "-y 国債"].some(function (word) { return title.indexOf(word) >= 0; })) {
      return {
        summary:"国債入札は単純な予想差より、テール・応札倍率・間接入札比率など需給の質が重要。弱い入札なら金利上昇が翌日にも残りやすい。",
        continueIf:"入札後も" + c.rate + "が高止まりし、" + c.fx + "や" + c.stock + "へ波及する。",
        changeIf:"入札後の金利変化が巻き戻される、または後続の重要材料で金利方向が反転する。"
      };
    }

    if (["原油在庫", "crude oil inventories", "eia crude"].some(function (word) { return title.indexOf(word) >= 0; }) && delta !== null) {
      return delta > 0 ? {
        summary:"予想以上の在庫増は原油の需給緩和材料。WTIの上値を抑え、持続すればインフレ期待をやや低下させる方向。",
        continueIf:"WTIが翌営業日も弱く、製品在庫や稼働率も需給緩和を示す。",
        changeIf:"OPEC方針、地政学、ドル、需要見通しなど、より強い材料が逆方向に出る。"
      } : {
        summary:"予想以上の在庫減は原油の需給引き締まり材料。WTIを支え、持続すればインフレ期待を押し上げる方向。",
        continueIf:"WTIが翌営業日も強く、製品在庫や稼働率も需給引き締まりを示す。",
        changeIf:"OPEC方針、地政学、ドル、需要見通しなど、より強い材料が逆方向に出る。"
      };
    }

    if (["cpi", "pce", "ppi", "物価", "インフレ"].some(function (word) { return title.indexOf(word) >= 0; }) && delta !== null) {
      if (record.country === "日本") {
        return delta > 0 ? {
          summary:"インフレ上振れは日銀の正常化観測を支えやすく、日本金利上昇・円高方向。円高が強まれば日経225先物には重し。",
          continueIf:"日本国債利回りと円が翌営業日も同方向に動き、政策金利の織り込みが変化する。",
          changeIf:"金利が逆行する、後続指標が反対方向、または中銀発言で政策見通しが反転する。"
        } : {
          summary:"インフレ下振れは日銀の正常化観測を弱めやすく、日本金利低下・円安方向。円安が続けば日経225先物には支え。",
          continueIf:"日本国債利回りと円が翌営業日も同方向に動き、政策金利の織り込みが変化する。",
          changeIf:"金利が逆行する、後続指標が反対方向、または中銀発言で政策見通しが反転する。"
        };
      }
      return delta > 0 ? {
        summary:"インフレ上振れは利下げ期待を後退させやすく、" + c.rate + "上昇・" + c.fx + "高が基本線。株と金には逆風になりやすい。",
        continueIf:"翌営業日も" + c.rate + "が上昇し、政策金利の織り込みが同方向へ変化する。",
        changeIf:"金利が逆行する、後続の雇用・景気指標が反対方向、または中銀発言で政策織り込みが反転する。"
      } : {
        summary:"インフレ下振れは利下げ期待を支えやすく、" + c.rate + "低下・" + c.fx + "安が基本線。株と金には支援材料になりやすい。",
        continueIf:"翌営業日も" + c.rate + "が低下し、政策金利の織り込みが同方向へ変化する。",
        changeIf:"金利が逆行する、後続の雇用・景気指標が反対方向、または中銀発言で政策織り込みが反転する。"
      };
    }

    if (["雇用", "失業", "賃金", "payroll", "jobless", "unemployment", "claims"].some(function (word) { return title.indexOf(word) >= 0; })) {
      var weak = judgement.indexOf("雇用弱") >= 0;
      return weak ? {
        summary:"雇用弱含みは利下げ期待を支え、" + c.rate + "低下・" + c.fx + "安に傾きやすい。株は金利低下が支えになる一方、景気懸念が強いと上値が重くなる。",
        continueIf:"翌営業日も" + c.rate + "と" + c.fx + "が同方向を維持し、他の雇用指標も弱さを示す。",
        changeIf:"賃金・雇用者数・失業率など他の雇用指標が逆方向、または金利市場が政策見通しを変えない。"
      } : {
        summary:"雇用の強さは利下げ期待を後退させ、" + c.rate + "上昇・" + c.fx + "高に傾きやすい。株は景気の強さと金利上昇の綱引き。",
        continueIf:"翌営業日も" + c.rate + "と" + c.fx + "が同方向を維持し、他の雇用指標も強さを示す。",
        changeIf:"他の雇用指標が逆方向、または金利市場が政策見通しを変えない。"
      };
    }

    if (["gdp", "国内総生産"].some(function (word) { return title.indexOf(word) >= 0; }) && delta !== null) {
      return delta > 0 ? {
        summary:"景気上振れは" + c.fx + "と景気敏感株を支えやすい一方、" + c.rate + "が大きく上昇するとグロース株には逆風。",
        continueIf:"翌営業日に" + c.stock + "と" + c.fx + "が景気判断を追認し、金利方向と矛盾しない。",
        changeIf:"同時発表のインフレ・雇用指標が逆方向、または金利上昇が株の景気評価を打ち消す。"
      } : {
        summary:"景気下振れは" + c.fx + "と景気敏感株の重し。金利低下は一部株式を支えるが、景気懸念が強い場合はリスク回避が優勢になりやすい。",
        continueIf:"翌営業日に" + c.stock + "と" + c.fx + "が景気判断を追認する。",
        changeIf:"同時発表のインフレ・雇用指標が逆方向、または後続材料で景気判断が反転する。"
      };
    }

    return {
      summary:"予想差だけでは翌日の方向を固定しない。金利・為替・株式の複数市場が同じ解釈を示すかを確認する。",
      continueIf:c.rate + "、" + c.fx + "、" + c.stock + "のうち複数が翌営業日も同方向に推移する。",
      changeIf:"市場間で方向がそろわない、または後続のより重要な材料が解釈を上書きする。"
    };
  }

  function addLine(parent, label, value) {
    var line = document.createElement("div");
    var strong = document.createElement("strong");
    strong.textContent = label;
    line.appendChild(strong);
    line.appendChild(document.createTextNode(value));
    parent.appendChild(line);
  }

  function processTable() {
    if (typeof completedRecords === "undefined") return;
    var body = document.getElementById("completedEventList");
    if (!body) return;
    var table = body.closest("table");
    if (!table) return;

    var section = table.closest("section");
    if (section) {
      var heading = section.querySelector(".panel-title");
      if (heading) {
        var badge = heading.querySelector(".badge");
        heading.textContent = "終了した重要イベント｜今後の相場影響シナリオ";
        if (badge) heading.insertBefore(badge, heading.firstChild);
      }
      var note = section.querySelector(".footer-note");
      if (note) note.textContent = "発表後5分・30分の値動きではなく、結果の予想差と政策含意をもとに、翌日以降の相場への影響シナリオを表示します。実際の持続性は後続の金利・為替・株・商品で確認します。";
    }

    var head = table.querySelector("thead tr");
    if (head) {
      if (head.cells.length === 12) {
        head.deleteCell(10);
        head.deleteCell(9);
      }
      if (head.cells[9]) head.cells[9].textContent = "今後の相場影響シナリオ";
    }

    Array.prototype.slice.call(body.querySelectorAll("tr:not(.completed-detail-row)")).forEach(function (row) {
      var button = row.querySelector("[data-completed-id]");
      if (!button) {
        if (row.cells.length === 1 && row.cells[0].classList.contains("empty")) row.cells[0].colSpan = 11;
        return;
      }
      var record = completedRecords.find(function (item) { return String(item.event_id) === String(button.dataset.completedId); });
      if (!record) return;
      var impact = forwardImpact(record);
      if (row.cells.length === 12) {
        row.deleteCell(10);
        row.deleteCell(9);
        var td = document.createElement("td");
        td.className = "forward-impact-cell";
        td.textContent = impact.summary;
        row.insertBefore(td, row.cells[9]);
      } else if (row.cells[9]) {
        row.cells[9].className = "forward-impact-cell";
        row.cells[9].textContent = impact.summary;
      }
      if (row.cells[8]) row.cells[8].textContent = correctedJudgement(record);

      var detail = body.querySelector('[data-detail-for="' + CSS.escape(String(record.event_id)) + '"]');
      if (!detail) return;
      if (detail.cells[0]) detail.cells[0].colSpan = 11;
      var boxes = detail.querySelectorAll(".completed-detail-box > div");
      if (boxes.length < 2) return;

      var firstTitle = boxes[0].querySelector("h4");
      if (firstTitle) firstTitle.textContent = "結果とサプライズ";
      var firstP = boxes[0].querySelector("p");
      if (firstP) {
        firstP.replaceChildren();
        addLine(firstP, "前回：", record.previous || "取得不能");
        addLine(firstP, "市場予想：", record.forecast || "取得不能");
        addLine(firstP, "結果：", record.actual || "取得不能");
        addLine(firstP, "予想差：", record.surprise || "取得不能");
        addLine(firstP, "判定：", correctedJudgement(record));
      }
      var firstParagraphs = boxes[0].querySelectorAll("p");
      if (firstParagraphs.length > 1) firstParagraphs[1].textContent = record.details || "結果の内容を確認します。";

      var secondTitle = boxes[1].querySelector("h4");
      if (secondTitle) secondTitle.textContent = "今後の相場影響シナリオ";
      var secondP = boxes[1].querySelector("p");
      if (secondP) {
        secondP.replaceChildren();
        addLine(secondP, "基本シナリオ：", impact.summary);
        addLine(secondP, "影響が続く条件：", impact.continueIf);
        addLine(secondP, "見方を変える条件：", impact.changeIf);
        addLine(secondP, "関連市場：", Array.isArray(record.related_markets) ? record.related_markets.join("・") : "確認対象なし");
      }
    });

    table.style.minWidth = "1480px";
  }

  function install() {
    processTable();
    var body = document.getElementById("completedEventList");
    if (!body) return;
    var observer = new MutationObserver(function () {
      observer.disconnect();
      processTable();
      observer.observe(body, {childList:true, subtree:true});
    });
    observer.observe(body, {childList:true, subtree:true});

    var style = document.createElement("style");
    style.textContent = ".completed-table th:nth-child(10),.completed-table td:nth-child(10){min-width:330px}.completed-table th:nth-child(11),.completed-table td:nth-child(11){min-width:90px;width:90px}.completed-table th:nth-child(11)::after{content:none!important}.completed-table .completed-event-row>td:nth-child(10):before{content:\"今後の相場影響シナリオ\";display:block;margin-bottom:4px;color:#0b55c8;font-weight:1000;font-size:12px}.forward-impact-cell{line-height:1.55;color:#173968;font-weight:750}.completed-detail-box strong{color:#0b3f91}";
    document.head.appendChild(style);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", install);
  else install();
})();

