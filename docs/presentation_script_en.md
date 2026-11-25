Good morning, this is Group 7. And my project is called PlanB. It is an AI helper for travel plans.  
The idea is simple: the LLM understands, the code checks and does the math, and you decide.

So what can PlanB do?  
First, you tell PlanB about your trip in one paragraph: your dates, where you want to go, what you like, and what you've already booked, like your flight and hotel. Then it plans your days around what you want and what you've booked.  
Second, you can change the plan by chat, like "I don't want to go to this place", and it will give you other options.  
And third, if something unexpected gets in the way, like heavy rain, a closed museum or a delayed train, PlanB only changes the part that's affected, and tells you if it costs anything extra.

So, why not just ask an LLM to do all this?  
We asked a 550-billion-parameter model to add one more day. It found the right bookings, and the plan looks good.  
But look at the price: it forgot the flight change fee, so the total is wrong. And it made this mistake 3 out of 4 times.

So PlanB splits the work.  
The LLM just figures out what the user wants.  
Then the code takes over: it checks the rules, changes only what's affected, and does the math.  
At the end, the LLM explains, and gives the plan to the user to approve.

Here's the same request in PlanB.  
Only the flight and the hotel are affected, and the extra cost is correct. Every part of it comes from a booking rule.

So how do we know it works?  
We wrote two test sets by hand: 10 cases where the trip changes, and 13 about planning and editing a trip.  
We compared four methods. In the first two, the LLM does everything: one with a simple prompt, and one with a list of rules. Then there's PlanB.  
And the last one is a check for ourselves: we fill in the request correctly by hand and give it to PlanB. So if PlanB still fails, the problem is in our code. If it works, then the mistakes came from the LLM reading the request.  
We used a small and a big free model, and a case only counts if everything is right, including the money.

And here's what we found.  
With the small model, the LLM-only methods almost always fail, while PlanB still solves more than half.  
With the big model, they plan well, but still get the money wrong.  
And when PlanB gets the correct request, it solves every case. So its mistakes come from the reading, not from our code.  
This also matters for cost. With the small model, PlanB uses about five to seven times fewer tokens, and on a CPU it answers in under a minute, not several minutes. So even a small free model becomes really useful.

So what did I learn from this project?  
First, LLMs are not always right. Even a very big model forgot a fee. For hard numbers and rules, code is more precise.  
Second, writing the rules in the prompt is not enough. Even with a full list of rules, the small model still got almost every case wrong. The same rules work much better in code.  
And third, if the LLM only has a small job, like understanding the request, even a small free model becomes useful, and it costs much less.  
Next, I'll add more test cases and test with more models for the final report. So that's all for today's presentation, thank you!
