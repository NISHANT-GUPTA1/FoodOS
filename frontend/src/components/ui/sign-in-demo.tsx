import { useNavigate } from 'react-router-dom';
import { SignInPage } from "@/components/ui/sign-in";
import type { Testimonial } from "@/components/ui/sign-in";

// Avatars are inline SVG initials, not remote photos. These were Unsplash
// URLs on the one screen that is guaranteed to be projected first, and the
// H34 rehearsal runs with the wifi off — three broken image frames above the
// login form is a bad opening line.
const foodosTestimonials: Testimonial[] = [
  {
    avatarSrc: "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNTAiIGhlaWdodD0iMTUwIj48cmVjdCB3aWR0aD0iMTUwIiBoZWlnaHQ9IjE1MCIgcng9Ijc1IiBmaWxsPSIjMDQ3ODU3Ii8+PHRleHQgeD0iNzUiIHk9Ijc1IiBmb250LWZhbWlseT0iSW50ZXIsc3lzdGVtLXVpLHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iNTgiIGZvbnQtd2VpZ2h0PSI2MDAiIGZpbGw9IiNmZmZmZmYiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGRvbWluYW50LWJhc2VsaW5lPSJjZW50cmFsIj5TQzwvdGV4dD48L3N2Zz4=",
    name: "Sarah Chen",
    handle: "@sarah_foodos",
    text: "FoodOS reduced our kitchen prep waste by 34% in our first month across 12 locations."
  },
  {
    avatarSrc: "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNTAiIGhlaWdodD0iMTUwIj48cmVjdCB3aWR0aD0iMTUwIiBoZWlnaHQ9IjE1MCIgcng9Ijc1IiBmaWxsPSIjMGY3NjZlIi8+PHRleHQgeD0iNzUiIHk9Ijc1IiBmb250LWZhbWlseT0iSW50ZXIsc3lzdGVtLXVpLHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iNTgiIGZvbnQtd2VpZ2h0PSI2MDAiIGZpbGw9IiNmZmZmZmYiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGRvbWluYW50LWJhc2VsaW5lPSJjZW50cmFsIj5NSjwvdGV4dD48L3N2Zz4=",
    name: "Marcus Johnson",
    handle: "@marcustech",
    text: "The decision intelligence spine and RSL tracking save us thousands of rupees daily."
  },
  {
    avatarSrc: "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNTAiIGhlaWdodD0iMTUwIj48cmVjdCB3aWR0aD0iMTUwIiBoZWlnaHQ9IjE1MCIgcng9Ijc1IiBmaWxsPSIjMDY1ZjQ2Ii8+PHRleHQgeD0iNzUiIHk9Ijc1IiBmb250LWZhbWlseT0iSW50ZXIsc3lzdGVtLXVpLHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iNTgiIGZvbnQtd2VpZ2h0PSI2MDAiIGZpbGw9IiNmZmZmZmYiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGRvbWluYW50LWJhc2VsaW5lPSJjZW50cmFsIj5FUjwvdGV4dD48L3N2Zz4=",
    name: "Elena Rostova",
    handle: "@elena_ops",
    text: "Automated B2B rescue rerouting is intuitive, reliable, and keeps inventory fresh."
  },
];

// Farm gate, and all four committed locally — the sign-in screen is the first thing on
// the projector, and the H34 rehearsal runs with the wifi off.
const foodosHeroImages = [
  "/farm-field-sunrise.jpg",
  "/market-produce-crates.jpg",
  "/market-vegetables.jpg",
  "/crop-seedlings.jpg"
];

const SignInPageDemo = () => {
  const navigate = useNavigate();

  const handleSignIn = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const data: Record<string, any> = {};
    formData.forEach((value, key) => {
      data[key] = value;
    });
    console.log("FoodOS Sign In submitted:", data);
    navigate('/today');
  };

  const handleGoogleSignIn = () => {
    console.log("FoodOS Google Workspace Sign-In");
    navigate('/today');
  };
  
  const handleResetPassword = () => {
    alert("Password reset link sent to your enterprise email.");
  };

  const handleCreateAccount = () => {
    alert("Enterprise onboarding request submitted. An admin will contact your kitchen node.");
  };

  return (
    <div className="bg-slate-50 text-slate-900 min-h-screen">
      <SignInPage
        title={<span className="font-extrabold text-slate-900 tracking-tight">FoodOS Enterprise</span>}
        description="Access your AI Decision Intelligence Portal and Kitchen Waste Analytics"
        heroImageSrc={foodosHeroImages}
        testimonials={foodosTestimonials}
        onSignIn={handleSignIn}
        onGoogleSignIn={handleGoogleSignIn}
        onResetPassword={handleResetPassword}
        onCreateAccount={handleCreateAccount}
      />
    </div>
  );
};

export default SignInPageDemo;
