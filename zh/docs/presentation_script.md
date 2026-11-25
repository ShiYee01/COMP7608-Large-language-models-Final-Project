# Presentation 讲稿（4 分钟版，对应 pptx）

对应文件：`PlanB_Proposal_Presentation.pptx`（正文 8 页，第 9 页起是附录）。

老师的安排：每组 **4 分钟**，剩 1 分钟时老师会举手。下面这版照着讲大约 3 分半，留了半分钟余量。语气就像跟同学聊天，英文都是简单的词，说错一两个字没关系。

每页三块："记住这句"是这页的核心；"中文意思"帮你理解；"英文这样说"就是上台要说的话，pptx 里每页的演讲者备注也是这段英文。每页开头那句是过渡句，最好背熟，讲起来会很顺。

**时间检查点**

| 讲完第几页 | 大约用时 |
|---|---|
| 第 3 页 | 1 分 10 秒 |
| 第 5 页 | 1 分 55 秒 |
| 第 7 页 | 3 分 00 秒 |
| 第 8 页 | 3 分 30 秒 |

**老师举手（还剩 1 分钟）时，你应该正在讲第 7 页左右。** 如果那时还在第 5、6 页，就跳过第 6 页的细节，直接说 "In short, PlanB did much better, especially on money"，然后翻到第 8 页讲完体会。

整个故事：PlanB 能做三件事 → 但直接用 LLM 会算错钱 → 所以分工 → 演示 → 怎么测 → 结果 → 我学到了什么。

---

## 第 1 页　封面（10 秒）

记住这句：LLM 负责听懂，代码负责检查和算钱，你来决定。

中文意思：大家好，我是 Zhang Yupeng，我的项目叫 PlanB，是一个帮你做旅行计划的 AI 助手。思路很简单：LLM 负责听懂，代码负责检查和算账，最后你来做决定。

英文这样说：
> Hi everyone, I'm Zhang Yupeng, and my project is PlanB, an AI helper for travel plans.
> The idea is simple: the LLM understands, the code checks and does the math, and you decide.

---

## 第 2 页　What PlanB does（30 秒）

记住这句：一段话出行程，聊天改行程，出状况就重新安排。

中文意思：那 PlanB 能做什么呢？三件事。第一，你用一段话写下旅行，它帮你排出每天的行程，而且不动你订好的东西。第二，你可以聊天改行程，比如"我不想去浅草寺了"，它会给你几个选项。第三，如果出了状况，比如下雨或者多待一天，它只改受影响的部分，还告诉你要多花多少钱。

英文这样说：
> So what can PlanB do? Three things.
> First, you write your trip in one paragraph, and it makes a day-by-day plan, without touching your bookings.
> Second, you can change the plan by chat, like "I don't want to go to Senso-ji", and it gives you options.
> And third, if something changes, like rain or an extra day, it only changes what's affected and tells you the extra cost.

---

## 第 3 页　Even a 550B model gets the price wrong（30 秒）

记住这句：大模型漏了 200 块改签费，说 950，其实是 1150。

中文意思：那为什么不直接让 LLM 来做？我们试过。我们让一个 5500 亿参数的模型帮忙多加一天。订单找对了，听起来也不错。但你看价格，它漏了 200 块的改签费，说 950，正确答案是 1150。小模型就更糟了。

英文这样说：
> Now, why not just ask an LLM to do all this? Well, we tried.
> We asked a 550-billion-parameter model to add one more day. It found the right bookings, and it sounds good.
> But look at the price: it forgot the 200-yuan change fee. It said 950, but the right answer is 1,150.
> And small models are even worse.

说到 "But look at the price" 时停一下，指一下 ¥950。

---

## 第 4 页　How PlanB splits the work（25 秒）

记住这句：LLM 只负责听懂，剩下的交给代码。

中文意思：所以 PlanB 把活分开。LLM 只负责搞清楚你想要什么。之后交给普通代码：检查规则，只改受影响的部分，再把钱算出来。不知道的就说"不知道"，不会当成 0。最后 LLM 解释结果，你来决定。

英文这样说：
> So PlanB splits the work.
> The LLM just figures out what you want.
> Then normal code takes over: it checks the rules, changes only what's affected, and does the math. If it doesn't know something, it says "unknown", not zero.
> At the end, the LLM explains, and you decide.

---

## 第 5 页　Demo: stay one more day（20 秒）

记住这句：200 加 350 加 600，等于 1150。

中文意思：这是同一个请求在 PlanB 里的结果。只有机票和酒店受影响，费用是 200 加 350 加 600，一共 1150，全部来自订单规则。

英文这样说：
> Here's the same request in PlanB.
> Only the flight and the hotel are affected, and the cost is 200 plus 350 plus 600, so 1,150, all from the booking rules.

---

## 第 6 页　How we test（35 秒）

记住这句：两组手写测试、四种方法、两个模型，全对才算对。

中文意思：那怎么知道它真的管用？我们手写了两组测试：10 个是旅途中出状况，13 个是新建和修改行程。比较了四种方法：两种是让 LLM 全包，一种只给普通提示，一种给一串规则；然后是 PlanB；还有给 PlanB 正确请求的版本。我们用了一小一大两个免费模型，而且一个案例要全对，包括钱，才算做对。

英文这样说：
> So how do we know it works?
> We wrote two test sets by hand: 10 cases where the trip changes, and 13 about planning and editing a trip.
> We compared four methods: two where the LLM does everything, one with a simple prompt and one with a list of rules; then PlanB; and PlanB with the correct request.
> We used a small and a big free model, and a case only counts if everything is right, including the money.

---

## 第 7 页　Results: number of cases solved（30 秒）

记住这句：小模型下 PlanB 对 14 个，大模型下别人算错钱，读对了就 23 个全对。

中文意思：来看结果。用小模型时，LLM 全包的方法几乎全错，PlanB 做对了 23 个里的 14 个。用大模型时，它们行程排得不错，但钱还是算错。而只要 PlanB 把请求读对，23 个全对。

英文这样说：
> And here's what we found.
> With the small model, the LLM-only methods almost always fail, but PlanB gets 14 out of 23.
> With the big model, they plan well, but still get the money wrong.
> And when PlanB reads the request correctly, it gets all 23 right.

先指加粗的 PlanB 那一行，再指最后一行。

---

## 第 8 页　What I learned（30 秒）

记住这句：钱要交给代码，难的是读懂请求，小模型也要测。

中文意思：那我从这个项目学到了什么？第一，就算是大模型也会算错钱，所以规则和钱应该交给代码。第二，难的其实是读懂请求，而不是排行程。第三，一定也要用小模型测一测，它让我发现了大模型掩盖住的问题，甚至找出了我自己代码里的一个 bug。接下来，我会为期末报告加更多测试。谢谢大家！

英文这样说：
> So what did I learn?
> First, even a big LLM gets money wrong, so rules and money should be done by code.
> Second, the hard part is reading the request, not planning.
> And third, test with a small model too. It showed me problems the big model hid, and even a bug in my own code.
> Next, I'll add more test cases for the final report. Thank you!

这页是老师特别想听的"insights 和 lessons learned"，时间再紧也要讲到。

---

## 答疑小抄

被问到时先用一句话回答，需要的话再翻到对应的附录页。听不清可以说 "Sorry, could you say that again?"。

**问：评测是不是偏向你自己的方法？**
> Not really. I wrote the right answers by hand from the booking rules, and the same checker scores every method. The "LLM + rules" method even gets an extra list of rules.

（标准答案按订单规则手写，所有方法用同一个检查器，"LLM + rules"还多给了一份规则。）

**问：大模型已经很接近了，为什么还要 PlanB？**
> Good question. The big model still gets the money wrong, and it uses five to eight times more tokens. PlanB's answers are checked by code, and it also works with a small model.

（大模型还是算错钱，token 多 5 到 8 倍；PlanB 有代码检查，小模型也能用。）

**问：为什么小模型新建行程只有 2/8？**
> Yeah, that's the weak point. The small model misses things in long paragraphs, usually the return flight. When the request is read correctly, it's 8 out of 8. That's why PlanB shows you what it understood first.

（小模型读长段落会漏，最常见的是漏返程航班；读对了就是 8/8，所以 PlanB 会先让用户确认。）

**问：你发现的那个 bug 是什么？**
> The small model read a flight time wrong. Then my planner put a sightseeing stop too close to the airport, with not enough travel time. I fixed it, and the results didn't change.

（小模型读错了航班时间，规划器在去机场前排了一个景点，交通时间不够。已经修好，结果没有变化。）

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
