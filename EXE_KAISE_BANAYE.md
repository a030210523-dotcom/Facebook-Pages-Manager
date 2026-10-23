# .EXE kaise banaye — baghair Python install kiye software chalane ke liye

Final software **ek hi file** hogi: `FacebookPagesManager.exe`
Us file ko chalane ke liye **na Python chahiye, na koi aur application** — sirf Windows 10/11.
Double-click = software khul gaya. Customers ko bhi yehi ek file bhejni hai.

`.exe` banane ke 2 tareeqe hain (koi ek chun lein):

## Tareeqa 1 — Apne Windows PC par (sab se asaan)
1. Project folder ko Windows PC par rakhein.
2. **`BUILD_EXE_ONE_CLICK.bat`** par double-click karein.
3. Agar PC mein Python nahi hai to ye file **khud download/install** kar legi (sirf pehli dafa,
   sirf build karne ke liye). Phir libraries lagengi aur `.exe` ban jayegi.
4. Aakhir mein `dist` folder khul jayega — us mein `FacebookPagesManager.exe` tayyar hai.

## Tareeqa 2 — Online, PC par kuch install kiye baghair (GitHub)
1. github.com par free account banayein, nayi repository banayein.
2. Is poore project ko wahan upload kar dein (website par drag & drop ho jata hai).
3. Repository ke **Actions** tab mein build khud chalegi.
4. Khatam honay par **Artifacts** se `FacebookPagesManager-Windows` download kar lein —
   andar wahi single-file `.exe` hai.

## Saboot
Yehi single-file tareeqa bana kar test kiya gaya hai: ek 85 MB ki akeli file bani,
aur aisay mahol mein chalayi gayi jahan system mein Python mojood hi nahi tha —
software phir bhi khula aur chalta raha. Windows `.exe` bhi bilkul aisay hi banti hai,
sirf build Windows par ya GitHub (Windows) par hota hai.
