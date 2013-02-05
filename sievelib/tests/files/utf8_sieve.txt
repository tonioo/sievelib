require ["fileinto", "reject"];

# Filter: UTF8 Test Filter äöüß 汉语/漢語 Hànyǔ
if allof (header :contains ["Subject"] ["â‚¬ 300"]) {
    fileinto "Spam";
    stop;
}
