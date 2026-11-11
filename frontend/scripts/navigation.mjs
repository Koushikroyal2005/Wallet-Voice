// Same public consumer paths at every width; no hidden desktop-only controls.
export async function navigate(page, name) {
  const primary = {
    Home: "Home",
    Payments: "Inbox",
    Inbox: "Inbox",
    Pay: "Pay",
    Activity: "Activity",
  };
  if (primary[name])
    return page
      .getByRole("navigation", { name: "Main navigation" })
      .getByRole("button", { name: primary[name], exact: true })
      .click();
  await page
    .getByRole("button", { name: "Open account and Settings", exact: true })
    .click();
  if (name === "Auto-pay & security")
    return page
      .getByRole("button", { name: "Security & AutoPay", exact: true })
      .click();
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  return page
    .locator(".settings-list")
    .getByRole("button", { name, exact: true })
    .click();
}
