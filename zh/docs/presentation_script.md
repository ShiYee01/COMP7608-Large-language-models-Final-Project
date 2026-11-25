# Presentation 讲稿（4 分钟版，对应 pptx）

对应文件：`PlanB_Proposal_Presentation.pptx`（正文 8 页，第 9 页起是附录）。

老师的安排：每组 **4 分钟**，剩 1 分钟时老师会举手。下面这版照着讲大约 3 分 45 秒。语气就像跟同学聊天，英文都是简单的词，说错一两个字没关系。

每页三块："记住这句"是这页的核心；"中文意思"帮你理解；"英文这样说"就是上台要说的话，pptx 里每页的演讲者备注也是这段英文。每页开头那句是过渡句，最好背熟。

**时间检查点**

| 讲完第几页 | 大约用时 |
|---|---|
| 第 3 页 | 1 分 10 秒 |
| 第 5 页 | 1 分 45 秒 |
| 第 7 页 | 3 分 10 秒 |
| 第 8 页 | 3 分 45 秒 |

**老师举手（还剩 1 分钟）时，你应该正在讲第 7 页。** 如果那时还在第 6 页，就直接说 "In short, PlanB did much better, especially on money"，然后翻到第 8 页讲完体会。

整个故事：PlanB 能做三件事 → 但直接用 LLM 会算错钱 → 所以分工 → 演示 → 怎么测 → 结果 → 我学到了什么。

---

## 第 1 页　封面（10 秒）

记住这句：LLM 负责听懂，代码负责检查和算钱，你来决定。

中文意思：大家早上好，我们是第 7 组，我的项目叫 PlanB，是一个帮你做旅行计划的 AI 助手。思路很简单：LLM 负责听懂，代码负责检查和算账，最后你来做决定。

英文这样说：
> Good morning, this is Group 7. And my project is called PlanB. It is an AI helper for travel plans.
> The idea is simple: the LLM understands, the code checks and does the math, and you decide.

---

## 第 2 页　What PlanB does（35 秒）

记住这句：你告诉它订了什么，它围绕这些订单排行程；还能聊天改、出状况重新安排。

中文意思：那 PlanB 能做什么呢？三件事。第一，你用一段话告诉 PlanB 你的旅行：日期、想去哪、喜欢什么，还有你已经订好的东西，比如机票和酒店。然后它就围绕你想去的地方和你订好的东西，排出每天的行程。第二，你可以聊天改行程，比如"我不想去这个地方了"，它会给你其他的选项。第三，如果出了状况，比如下雨或者多待一天，它只改受影响的部分，还告诉你要多花多少钱。

英文这样说：
> So what can PlanB do?
> First, you tell PlanB about your trip in one paragraph: your dates, where you want to go, what you like, and what you've already booked, like your flight and hotel. Then it plans your days around what you want and what you've booked.
> Second, you can change the plan by chat, like "I don't want to go to this place", and it will give you other options.
> And third, if something changes, like rain or an extra day, it only changes what's affected and tells you the extra cost.

---

## 第 3 页　Even a 550B model gets the price wrong（30 秒）

记住这句：大模型漏了改签费，总价错了，4 次里错了 3 次。

中文意思：那为什么不直接让 LLM 来做？我们让一个 5500 亿参数的模型帮忙多加一天。订单找对了，行程看起来也不错。但你看价格，它漏了机票的改签费，所以总价是错的。而且同样的错误，4 次里出现了 3 次。

英文这样说：
> So, why not just ask an LLM to do all this?
> We asked a 550-billion-parameter model to add one more day. It found the right bookings, and the plan looks good.
> But look at the price: it forgot the flight change fee, so the total is wrong. And it made this mistake 3 out of 4 times.

说到 "But look at the price" 时停一下，指一下 ¥950。

---

## 第 4 页　How PlanB splits the work（25 秒）

记住这句：LLM 只负责听懂，剩下的交给代码。

中文意思：所以 PlanB 把活分开。LLM 只负责搞清楚用户想要什么。之后交给代码：检查规则，只改受影响的部分，再把钱算出来。最后 LLM 解释结果，把方案交给用户确认。

英文这样说：
> So PlanB splits the work.
> The LLM just figures out what the user wants.
> Then the code takes over: it checks the rules, changes only what's affected, and does the math.
> At the end, the LLM explains, and gives the plan to the user to approve.

---

## 第 5 页　Demo: stay one more day（15 秒）

记住这句：只动机票和酒店，费用算对了，每一笔都有依据。

中文意思：这是同一个请求在 PlanB 里的结果。只有机票和酒店受影响，算出来的额外费用是对的，而且每一部分都来自订单规则。

英文这样说：
> Here's the same request in PlanB.
> Only the flight and the hotel are affected, and the extra cost is correct. Every part of it comes from a booking rule.

---

## 第 6 页　How we test（45 秒）

记住这句：最后一种方法是给我们自己做检查的，用来分清是 LLM 读错了，还是代码错了。

中文意思：那怎么知道它真的管用？我们手写了两组测试：10 个是旅途中出状况，13 个是新建和修改行程。我们比较了四种方法。前两种是让 LLM 全包，一种只给普通提示，一种给一串规则。然后是 PlanB。最后一种是给我们自己做检查用的：我们手动把请求正确地填好，再交给 PlanB。这样如果 PlanB 还是做错，说明是我们的代码有问题；如果做对了，说明之前的错误是 LLM 读请求时读错了。我们用了一小一大两个免费模型，而且一个案例要全对，包括钱，才算做对。

英文这样说：
> So how do we know it works?
> We wrote two test sets by hand: 10 cases where the trip changes, and 13 about planning and editing a trip.
> We compared four methods. In the first two, the LLM does everything: one with a simple prompt, and one with a list of rules. Then there's PlanB.
> And the last one is a check for ourselves: we fill in the request correctly by hand and give it to PlanB. So if PlanB still fails, the problem is in our code. If it works, then the mistakes came from the LLM reading the request.
> We used a small and a big free model, and a case only counts if everything is right, including the money.

讲到第 4 种方法时，可以指着屏幕右边的第 4 条。

---

## 第 7 页　Results: number of cases solved（40 秒）

记住这句：小模型下别人几乎全错，大模型下别人算错钱，读对了 PlanB 就全对；而且小模型用 PlanB 又省又快。

中文意思：来看结果。用小模型时，LLM 全包的方法几乎全错，PlanB 还能做对一半以上。用大模型时，它们行程排得不错，但钱还是算错。而只要给 PlanB 正确的请求，它每个案例都做对了。所以 PlanB 的错误出在"读"这一步，不在我们的代码。这一点对成本也很重要：用小模型时，PlanB 用的 token 少 5 到 7 倍，在普通 CPU 上不到一分钟就能出结果，而不是好几分钟。所以就算是一个免费的小模型，也真的能用起来。

英文这样说：
> And here's what we found.
> With the small model, the LLM-only methods almost always fail, while PlanB still solves more than half.
> With the big model, they plan well, but still get the money wrong.
> And when PlanB gets the correct request, it solves every case. So its mistakes come from the reading, not from our code.
> This also matters for cost. With the small model, PlanB uses about five to seven times fewer tokens, and on a CPU it answers in under a minute, not several minutes. So even a small free model becomes really useful.

先指加粗的 PlanB 那一行，再指最后一行，讲到成本时指最下面那条 "Cheaper and faster"。

---

## 第 8 页　What I learned（35 秒）

记住这句：LLM 不是完全可靠的；让它和代码各做擅长的事；让用户来确认。

中文意思：那我从这个项目学到了什么？第一，LLM 不是完全可靠的，连很大的模型都会漏掉一笔费用；像这种硬性的数字和规则，用代码会更准。第二，最好的方式是让每一部分做自己擅长的事：LLM 擅长听懂人在说什么，代码擅长检查和计算，两者结合起来，比只用 LLM 可靠得多，连便宜的小模型都能用得上。第三，LLM 还是有可能理解错，所以要让用户参与进来：PlanB 会先把它理解的内容给用户看，用户确认了再往下走。接下来，我会为期末报告加更多测试案例，也会用更多模型来测试。今天的展示就到这里，谢谢大家！

英文这样说：
> So what did I learn from these experiments?
> First, LLMs are not always right. Even a very big model forgot a fee. For hard numbers and rules, code is more precise.
> Second, it works best when each part does what it's good at. The LLM understands what users mean, and the code checks and calculates. Together, they're more reliable than the LLM alone, and even a small, cheap model becomes useful.
> And third, the LLM can still misunderstand, so keep the user in the loop. PlanB shows what it understood, and the user confirms.
> Next, I'll add more test cases and test with more models for the final report. So that's all for today's presentation, thank you!

这页是老师特别想听的"insights 和 lessons learned"，时间再紧也要讲到。

---

## 答疑小抄

被问到时先用一句话回答，需要的话再翻到对应的附录页。听不清可以说 "Sorry, could you say that again?"。

**问：用户要上传订单截图或者凭证吗？PlanB 会自己去查订单吗？**
> No. You just tell PlanB in words what you booked. It doesn't search, check or book anything. It only plans around what you told it.

（不用。用户用文字告诉 PlanB 订了什么就行，PlanB 不查、不核对、也不订，只是围绕这些信息排行程。）

**问：为什么要测"PlanB + correct request"？**
> To find out where the mistakes come from. If PlanB still fails with the correct request, our code is wrong. It never failed, so all the mistakes came from the LLM reading the request.

（用来找出错误出在哪里。给了正确请求还错，就是代码的问题；它一次都没错，所以错误都是 LLM 读请求时产生的。）

**问：评测是不是偏向你自己的方法？**
> Not really. I wrote the right answers by hand from the booking rules, and the same checker scores every method. The "LLM + rules" method even gets an extra list of rules.

（标准答案按订单规则手写，所有方法用同一个检查器，"LLM + rules"还多给了一份规则。）

**问：大模型已经很接近了，为什么还要 PlanB？**
> Good question. The big model still gets the money wrong, and it uses five to eight times more tokens. PlanB's answers are checked by code, and it also works with a small model.

（大模型还是算错钱，token 多 5 到 8 倍；PlanB 有代码检查，小模型也能用。）

**问：为什么小模型新建行程只有 2/8？**
> Yeah, that's the weak point. The small model misses things in long paragraphs, usually the return flight. That's why PlanB shows you what it understood first, so you can fix it.

（小模型读长段落会漏，最常见的是漏返程航班；所以 PlanB 会先让用户确认，用户可以改。）

**问：规划都是代码做的，这还算 AI 项目吗？**
> I think so. The LLM handles all the language. My question is which jobs should go to the LLM and which to code, and the tests compare different ways of using LLMs.

（LLM 负责所有语言理解；我研究的是哪些活该交给 LLM、哪些该交给代码。）

**问：为什么选这两个模型？**
> I had no budget, so I used free open models. The small one is Qwen 2.5 3B running on a CPU, and the big one was the largest free open model I could use. Changing the model is just a setting.

（没预算，只用免费开源模型；换模型只要改设置。）

**问：价格和交通是真的吗？**
> No, it's all simulated data, and it's marked that way. PlanB never books, pays, or checks live prices.

（都是模拟数据，标清楚了；PlanB 不订票、不付款、不查实时价格。）

**问：接下来做什么？**
> I'll grow to about 40 cases and keep some only for testing. I'll also take out parts of PlanB one by one to see what really matters, and add a mid-size model.

（扩到约 40 个案例并留一部分只做测试；逐个拿掉模块看影响；再加一个中等模型。）
