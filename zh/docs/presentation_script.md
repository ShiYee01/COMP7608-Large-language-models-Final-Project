# Presentation 讲稿（5 分钟版，对应 pptx）

对应文件：`PlanB_Proposal_Presentation.pptx`（正文 8 页，第 9 页起是附录）。

老师给每人 4 到 5 分钟，照下面讲大概 4 分半。语气就像跟同学聊天一样，不用端着。英文都是简单的词，说错一两个字没关系，意思对就行。

每页三块："记住这句"是这页的核心，记住它就不会卡住；"中文意思"帮你理解；"英文这样说"就是你上台要说的话，pptx 里每页的演讲者备注也是这段英文。每页开头那句是**过渡句**，用来把上一页接过来，最好记熟，讲起来就会很顺。

整个故事连起来就是：PlanB 能做三件事 → 但直接用 LLM 会算错钱 → 所以我们分工 → 演示一下 → 那怎么知道它真的行？→ 看结果 → 总结。

---

## 第 1 页　封面（10 秒）

记住这句：LLM 负责听懂，代码负责检查和算钱，你来做决定。

中文意思：大家好，我是 Zhang Yupeng，我的项目叫 PlanB，是一个帮你做旅行计划的 AI 助手。思路其实挺简单的：LLM 负责听懂你说什么，代码负责检查和算账，最后拍板的是你自己。

英文这样说：
> Hi everyone, I'm Zhang Yupeng, and my project is called PlanB. It's an AI helper for travel plans.
> The idea is pretty simple: the LLM understands what you say, the code does the checking and the math, and you make the final call.

---

## 第 2 页　What PlanB does（40 秒）

记住这句：一段话出行程，聊天改行程，出状况就重新安排。

中文意思：那 PlanB 到底能做什么呢？简单说就三件事。第一，你只要用一段话写下你的旅行，比如日期、想去哪、喜欢什么、已经订了什么，PlanB 就帮你排出每天的行程，而且不会动你订好的东西。第二，想改哪里，直接跟它说就行，比如"我不想去浅草寺了"，它会给你几个选项挑。第三，如果旅途中出了状况，比如下雨了，或者想多待一天，PlanB 只改受影响的那部分，还会告诉你要多花多少钱。

英文这样说：
> So what can PlanB actually do? Basically, three things.
> First, you just write your trip in one paragraph: your dates, where you want to go, what you like, and what you've already booked. And PlanB turns that into a day-by-day plan, without touching your bookings.
> Second, if you want to change something, you just tell it. Like, "I don't want to go to Senso-ji anymore." And it gives you a few options to pick from.
> And third, if something goes wrong during the trip, say it rains, or you want to stay one more day, PlanB only changes the part that's affected, and it tells you how much extra you'll pay.

---

## 第 3 页　Even a 550B model gets the price wrong（35 秒）

记住这句：大模型漏了 200 块改签费，说 950，其实是 1150。

中文意思：大家可能会想，为什么不直接让 LLM 来做这些？其实我们试过。我们让一个很大的模型，有 5500 亿参数，帮忙把行程延长一天。看起来还不错对吧？订单找对了，解释也挺像样。但你看价格，它把 200 块的改签费给漏了，所以它说 950，正确答案其实是 1150。小模型就更糟了，会把你订好的晚餐挪走，甚至把整天都重新排一遍。

英文这样说：
> Now you might be thinking, why not just ask an LLM to do all this? Well, we tried that.
> We asked a really big model, 550 billion parameters, to add one more day to the trip. And it looks pretty good, right? It found the right bookings, and the explanation sounds fine.
> But look at the price. It forgot the 200-yuan change fee. So it said 950, but the real answer is 1,150.
> And smaller models are even worse. They move your booked dinner, or change the whole day.

---

## 第 4 页　How PlanB splits the work（35 秒）

记住这句：LLM 只负责听懂，剩下的交给代码。

中文意思：所以 PlanB 就把活分开干。LLM 只在一开始做一件事：搞清楚你想要什么。之后就交给普通代码：它会检查规则，比如营业时间、路上要多久；只改受影响的部分；然后按你的订单规则把钱算出来。如果有什么不知道的，它就老实说"不知道"，而不是随便当成 0。最后再由 LLM 把结果解释给你听，你说行还是不行。

英文这样说：
> So that's why PlanB splits the work.
> The LLM only does one thing at the start: it figures out what you want.
> After that, normal code takes over. It checks the rules, like opening hours and travel time. It only changes what's affected. And it does the math using your booking rules. If it doesn't know something, it just says "unknown", instead of guessing zero.
> Then at the end, the LLM explains the result, and you decide yes or no.

讲的时候可以用手指着图，从左上角顺着箭头绕一圈。

---

## 第 5 页　Demo: stay one more day（30 秒）

记住这句：200 加 350 加 600，等于 1150。

中文意思：好，我们来实际看一下。这是同一个请求，放到 PlanB 里的结果。可以看到只有两个订单受影响：返程机票和酒店。费用是 200 加 350 再加 600，一共 1150，而且每个数字都能对应到一条订单规则。还有一点，PlanB 不会替你订任何东西，最后还是你自己决定。

英文这样说：
> Okay, let's see it in action. Here's the same request, but in PlanB.
> You can see only two bookings are affected: the return flight and the hotel.
> And the cost is 200 plus 350 plus 600, which gives 1,150. Every number here comes from a booking rule.
> Also, PlanB never books anything for you. You still make the decision.

---

## 第 6 页　How we test（45 秒）

记住这句：两组手写测试、四种方法、两个模型，全对才算对。

中文意思：那我们怎么知道它真的管用呢？我们自己手写了两组测试。第一组 10 个，是旅途中出状况，比如下雨、延误。第二组 13 个，是新建行程和聊天修改。然后我们比了四种方法：前两种是 LLM 全包，一种只给普通提示，一种给一长串规则；第三种是 PlanB；最后一种是给 PlanB 正确的请求，这样就能看出错误是不是出在"读懂请求"这一步。这些方法我们都用两个免费模型试了，一个小的，一个大的。而且一个案例要每一项都对，包括钱，才算做对。

英文这样说：
> So how do we know it really works? Well, we built two test sets by hand.
> The first one has 10 cases where something changes during the trip, like rain or a delay. The second one has 13 cases about planning a trip, or changing it by chat.
> Then we compared four methods. In the first two, the LLM does everything: one with a simple prompt, and one with a long list of rules. The third one is PlanB. And the last one is PlanB with the correct request, so we can see if the mistakes come from reading the request.
> We tried all of them with two free models, a small one and a big one.
> And a case only counts as solved if everything is right, including the money.

讲的时候按"左上、右上、左下、右下"的顺序指，正好对应这几句。

---

## 第 7 页　Results: number of cases solved（40 秒）

记住这句：小模型下 PlanB 对 14 个，大模型下别人算错钱，读对了就 23 个全对。

中文意思：来看看结果。用小模型的时候，让 LLM 全包的两种方法几乎全错，但 PlanB 还是能做对 23 个里的 14 个。换成大模型，LLM 全包的方法行程排得还不错，但钱还是会算错。至于 PlanB，它的错误全都是小模型读长请求时读错了，只要把请求读对，23 个全都能做对。另外，它用的 token 还少了 5 到 8 倍。

英文这样说：
> And here's what we found.
> With the small model, the LLM-only methods almost always fail, but PlanB still gets 14 out of 23 right.
> With the big model, the LLM-only methods plan pretty well, but they still get the money wrong.
> As for PlanB, all its mistakes come from the small model misreading long requests. Once it reads the request correctly, it gets all 23 right.
> And on top of that, it uses five to eight times fewer tokens.

讲的时候可以先指表格里加粗的 PlanB 那一行，再指最后一行。

---

## 第 8 页　Summary（20 秒）

记住这句：语言给 LLM，规则和钱给代码，决定给用户。

中文意思：最后总结一下：语言交给 LLM，规则和钱交给代码，决定交给用户。当然，这些还只是初步结果，是我自己写的 23 个案例，所以接下来我会加更多的测试。我就讲到这里，谢谢大家！

英文这样说：
> So, to sum up: let the LLM handle the language, let the code handle the rules and the money, and let the user make the decision.
> Of course, these are still early results, from 23 cases I wrote myself, so next I'm going to add more test cases.
> That's it from me. Thank you!

---

## 答疑小抄

被问到时，先用一句话回答，需要的话再翻到对应的附录页。听不清问题的时候，可以先说 "Sorry, could you say that again?"，不丢人。

**问：评测是不是偏向你自己的方法？**
标准答案是我按订单规则手写的，不是 PlanB 算出来的；所有方法用的是同一个检查器，"LLM + rules"还多给了一份规则。
> Not really. I wrote the right answers by hand from the booking rules, and the same checker scores every method. The "LLM + rules" method even gets an extra list of rules.

**问：大模型已经很接近了，为什么还要 PlanB？**
大模型还是会算错钱，用的 token 是 PlanB 的 5 到 8 倍。PlanB 的结果是代码检查过的，换成小模型也能用。
> Good question. The big model still gets the money wrong, and it uses five to eight times more tokens. PlanB's answers are checked by code, and it also works with a small model.

**问：为什么小模型新建行程只有 2/8？**
小模型读长段落会漏东西，最常见的是漏掉返程航班。读对的时候是 8/8。所以 PlanB 会先把理解的内容给用户确认。
> Yeah, that's the weak point. The small model misses things in long paragraphs, usually the return flight. When the request is read correctly, it's 8 out of 8. That's why PlanB shows you what it understood first.

**问：规划都是代码做的，这还算 AI 项目吗？**
算。LLM 负责所有理解语言的部分，我研究的就是哪些事该交给 LLM、哪些该交给代码，实验比的也是 LLM 的不同用法。
> I think so. The LLM handles all the language. My question is which jobs should go to the LLM and which to code, and the tests compare different ways of using LLMs.

**问：为什么选这两个模型？**
没有预算，只用免费开源模型。小模型是在 CPU 上跑的 Qwen2.5-3B，大模型是当时能免费用的最大的开源模型。换模型只要改设置。
> I had no budget, so I used free open models. The small one is Qwen 2.5 3B running on a CPU, and the big one was the largest free open model I could use. Changing the model is just a setting.

**问：价格和交通是真的吗？**
不是，都是模拟数据，而且标清楚了。PlanB 不订票、不付款，也不查实时价格。
> No, it's all simulated data, and it's marked that way. PlanB never books, pays, or checks live prices.

**问：接下来做什么？**
扩到大约 40 个案例，留一部分只用来测试；拿掉 PlanB 的某个部分看影响；再加一个中等大小的模型。
> I'll grow to about 40 cases and keep some only for testing. I'll also take out parts of PlanB one by one to see what really matters, and add a mid-size model.
