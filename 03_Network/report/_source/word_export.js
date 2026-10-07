// Late-bound Word automation (works even when the Office interop type library is not registered).
// cscript //nologo word_export.js <in.docx> <out.pdf>
var docx = WScript.Arguments(0), pdf = WScript.Arguments(1);
var word = new ActiveXObject("Word.Application");
word.Visible = false; word.DisplayAlerts = 0;
try {
  var doc = word.Documents.Open(docx, false, false);
  for (var i = 1; i <= doc.TablesOfContents.Count; i++) doc.TablesOfContents.Item(i).Update();
  doc.Fields.Update();
  for (var j = 1; j <= doc.TablesOfContents.Count; j++) doc.TablesOfContents.Item(j).UpdatePageNumbers();
  doc.Save();
  doc.ExportAsFixedFormat(pdf, 17, false, 0);
  WScript.Echo("OK pdf pages=" + doc.ComputeStatistics(2));
  doc.Close(false);
} finally { word.Quit(); }
