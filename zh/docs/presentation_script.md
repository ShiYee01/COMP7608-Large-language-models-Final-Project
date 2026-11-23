# Presentation 讲稿（5 分钟版）

slides：https://claude.ai/artifact/W6BqH2EQvtxhDh4uFE4Pfh

老师给每人 4 到 5 分钟。正文一共 8 页，照着下面讲大概 4 分钟，留一点余量。第 8 页之后都是附录，只有被问到时才翻。

每页分三块：先是一句"记住这句"，记住它就不会卡住；然后是中文意思，帮你理解；最后是英文怎么说，正式讲的时候照这个说就行。英文句子都很短，不用背得一字不差，意思对就可以。

---

## 第 1 页　封面（10 秒）

记住这句：LLM 负责理解，代码负责检查和算钱，用户做决定。

中文意思：大家好，我是某某。我的项目叫 PlanB，是一个 AI 旅行助手。思路很简单：LLM 负责理解，代码负责检查和算钱，最后由用户做决定。

英文这样说：
> Hi everyone, I'm [name]. My project is PlanB, an AI travel copilot.
> The idea is simple: the LLM understands, the code checks and calculates, and the user decides.

---

## 第 2 页　PlanB 能做什么（40 秒）

记住这句：一段话出行程，聊天改行程，出状况就重新规划。

中文意思：PlanB 能做三件事。第一，你用一段话描述旅行，比如日期、想去的地方、喜欢什么、已经订了什么，它就给你一份每天的行程，订好的东西不会被动。第二，你可以直接聊天改行程，比如说"我不想去浅草寺了"，它会给你几个选项让你挑。第三，旅途中出了状况，比如下雨或者想多待一天，它只改受影响的部分，还会告诉你准确要多花多少钱。

英文这样说：
> PlanB does three things.
> First, you describe your trip in one paragraph: the dates, the places you want to see, what you like, and what you already booked. It gives you a daily plan, and your bookings stay fixed.
> Second, you can change the plan by chat. For example: "I don't want to go to Senso-ji any more." It gives you a few options to choose from.
> Third, when something changes during the trip, like rain or staying one more day, it only changes what is affected, and it tells you the exact extra cost.

---

## 第 3 页　问题：大模型也会算错钱（35 秒）

记住这句：大模型漏了 200 块改签费，说 950，其实是 1150。

中文意思：那为什么不直接让 LLM 来做？我们试过。我们让一个 5500 亿参数的大模型处理"多待一天"，它找对了受影响的订单，解释也写得很像样，但是漏掉了 200 块的改签费。它说要多付 950，正确答案是 1150。小模型更糟，会把订好的晚餐挪走，甚至整天重写。

英文这样说：
> Why not just ask an LLM to do all this? We tried.
> We asked a 550-billion-parameter model to extend the trip by one day. It found the right bookings, and the explanation looks good.
> But it forgot the 200-yuan change fee. It said 950. The right answer is 1,150.
> Small models are even worse. They move booked dinners and rewrite whole days.

---

## 第 4 页　PlanB 怎么做（35 秒）

记住这句：LLM 只读懂，难的部分交给代码。

中文意思：所以 PlanB 把工作分开。LLM 只负责读懂用户的话，把它变成结构化的数据。难的部分交给普通代码：检查营业时间、交通时间和订单，只改受影响的地方，再按订单规则把钱算出来。不知道的就说不知道，不会当成 0。最后 LLM 把结果用人话解释一遍，用户点批准才算数。

英文这样说：
> So PlanB splits the work.
> The LLM only reads the request and turns it into structured data.
> Then normal code does the hard part. It checks opening hours, travel time and bookings, changes only what is affected, and calculates the cost from the booking rules. If something is unknown, it says unknown, not zero.
> At the end, the LLM explains the result, and the user approves.

讲的时候可以用手指着图，从左上角顺着箭头绕一圈。

---

## 第 5 页　演示：多待一天（30 秒）

记住这句：200 加 350 加 600，等于 1150。

中文意思：这是同一个请求在 PlanB 里的结果。只有返程机票和酒店受影响。费用是 200 改签费，加 350 差价，加 600 多住一晚，一共 1150，每个数字都来自订单规则。PlanB 不会自己去订票，最后还是用户决定。

英文这样说：
> Here is the same request in PlanB.
> Only the return flight and the hotel are affected.
> The cost is 200 plus 350 plus 600, so 1,150, and every number comes from a booking rule.
> Nothing is booked automatically. The user still decides.

---

## 第 6 页　结果 1：重新规划（40 秒）

记住这句：小模型 8/10，大模型 10/10，大模型的基线还是会算错钱。

中文意思：我们用 10 个场景、两个免费模型做了测试，一个是 3B 的小模型，一个是 550B 的大模型。用小模型时，直接让 LLM 改的方法几乎全失败，PlanB 做对了 8 个。用大模型时，直接让 LLM 改也能排出不错的行程，但钱还是会算错，PlanB 是 10 个全对。

英文这样说：
> We tested this on 10 scenarios with two free models: a small 3B model and a large 550B model.
> With the small model, the normal LLM methods almost always fail, but PlanB gets 8 out of 10.
> With the large model, the normal methods plan well, but they still get the money wrong. PlanB gets 10 out of 10.

讲到"plan well"的时候语气可以坦白一点，承认大模型确实不错，老师会觉得你诚实。

---

## 第 7 页　结果 2：新功能（30 秒）

记住这句：小模型读长段落会读漏，读对了就全对。

中文意思：新建行程和聊天修改这两个新功能，我们又测了 13 个场景，规律一样。PlanB 的弱点是小模型读长段落时会读漏，比如漏掉返程航班。但只要读对了，PlanB 就全部做对。所以它在排行程之前，会先把理解的内容给你看一遍。

英文这样说：
> We also tested the new features, trip setup and chat edits, on 13 more scenarios. The pattern is the same.
> PlanB's weak point is reading a long request with a small model, for example missing a flight.
> But when the request is read correctly, PlanB gets everything right. That's why it shows you what it understood before it plans.

---

## 第 8 页　总结（20 秒）

记住这句：语言给 LLM，规则和钱给代码，决定给用户。

中文意思：我想说的就是：语言交给 LLM，规则和钱交给代码，决定交给用户。现在是 23 个我自己写的场景上的初步结果，接下来会加更多测试。谢谢大家！

英文这样说：
> So my main message: let the LLM do the language, let code do the rules and the money, and let the user decide.
> These are early results on 23 scenarios I wrote myself, so next I will add more test cases.
> Thank you!

---

## 答疑小抄

被问到时先用一句话回答，需要的话再翻到对应的附录页。

**问：评测是不是偏向你自己的方法？**
标准答案是我按订单规则手写的，不是 PlanB 算出来的；所有方法用同一个检查器打分，基线还多给了一份详细规则。
> The answers were written by hand from the booking rules, and the same checker scores every method. The baseline even gets an extra list of rules.

**问：大模型已经很接近了，为什么还要 PlanB？**
大模型还是会算错钱，而且用的 token 是 PlanB 的 5 到 6 倍。PlanB 的结果是代码检查过的，换成小模型也能用。
> The large model still gets the money wrong, and it uses five to six times more tokens. PlanB's answers are checked by code, and it also works with a small model.

**问：为什么小模型新建行程只有 2/8？**
小模型读长段落会漏东西，最常见的是漏掉返程航班。读对的时候是 8/8。所以 PlanB 会先复述给用户确认，下一步还会加一个规则检查。
> The small model misses things in long paragraphs, usually the return flight. When the request is read correctly, it's 8 out of 8. That's why PlanB reads it back to the user first.

**问：规划都是代码做的，这还算 AI 项目吗？**
算。LLM 负责所有理解语言的部分，我研究的就是哪些事该交给 LLM、哪些该交给代码，实验比的也是 LLM 的不同用法。
> Yes. The LLM handles all the language. My question is which jobs should go to the LLM and which to code, and the experiments compare different ways of using LLMs.

**问：为什么选这两个模型？**
没有预算，只用免费开源模型。小模型是在 CPU 上跑的 Qwen2.5-3B，大模型是当时能免费调用的最大的开源模型。换模型只要改配置。
> I had no budget, so I used free open models. The small one is Qwen 2.5 3B running on a CPU, and the large one was the biggest free open model available. Switching models is just a config change.

**问：价格和交通是真的吗？**
不是，都是模拟数据，而且标清楚了。PlanB 不订票、不付款，也不查实时价格。
> No, it's simulated data, and it's labelled as simulated. PlanB never books, pays or checks live prices.

**问：接下来做什么？**
扩到大约 40 个场景并留一部分做测试集，做消融实验，再加一个中等大小的模型。
> I'll grow to about 40 scenarios with a held-out test set, run ablations, and add a mid-size model.
