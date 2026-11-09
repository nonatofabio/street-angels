(function () {
  var q = document.getElementById('q'), owner = document.getElementById('owner'), grid = document.getElementById('grid'),
      count = document.getElementById('count'), chips = document.querySelectorAll('#decades .chip'), decade = '';
  var cards = Array.prototype.slice.call(grid.querySelectorAll('.car-card'));
  function apply() {
    var s = (q.value || '').toLowerCase().trim(), o = owner.value, n = 0;
    cards.forEach(function (c) {
      var ok = (!o || c.dataset.owner === o) && (!decade || c.dataset.decade === decade) && (!s || c.dataset.text.indexOf(s) >= 0);
      c.style.display = ok ? '' : 'none'; if (ok) n++;
    });
    count.textContent = n === cards.length ? cards.length + ' cars' : n + ' of ' + cards.length + ' cars';
  }
  q.addEventListener('input', apply); owner.addEventListener('change', apply);
  chips.forEach(function (b) { b.addEventListener('click', function () {
    chips.forEach(function (x) { x.classList.remove('on'); }); b.classList.add('on'); decade = b.dataset.d; apply(); }); });
  apply();
})();
