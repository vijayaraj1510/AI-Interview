(() => {
  const category = document.getElementById("assessmentCategory");
  const topic = document.getElementById("assessmentTopic");
  if (!category || !topic) return;

  const syncTopics = () => {
    const selectedCategory = category.value;
    [...topic.options].forEach((option) => {
      if (!option.dataset.category) return;
      const visible = selectedCategory === "%" || option.dataset.category === selectedCategory;
      option.hidden = !visible;
      option.disabled = !visible;
    });
    if (topic.selectedOptions[0]?.disabled) topic.value = "%";
  };

  category.addEventListener("change", syncTopics);
  syncTopics();
})();
